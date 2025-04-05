import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                            QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, 
                            QProgressBar, QTextEdit, QGroupBox, QFormLayout, 
                            QSpinBox, QComboBox, QMessageBox, QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import os
import pandas as pd
import re
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import geopandas as gpd
import contextily as cx
import numpy as np
from matplotlib_scalebar.scalebar import ScaleBar
import matplotlib as mpl
from pypinyin import lazy_pinyin

# 导入地图选点模块
from map_selector import MapSelector

# Force matplotlib to use English fonts
mpl.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

class IsochroneWorker(QThread):
    progress_update = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, input_file=None, output_dir="isochrone_output", distance=1000, points_data=None):
        super().__init__()
        self.input_file = input_file
        self.output_dir = output_dir
        self.distance = distance
        self.points_data = points_data  # 添加直接接收坐标点数据的能力
        
    def run(self):
        try:
            coordinates = []
            
            # 判断使用哪种方式获取坐标数据
            if self.points_data:
                # 直接使用传入的坐标点数据
                coordinates = self.points_data
                self.progress_update.emit(f"Using {len(coordinates)} points from map selection", 5)
            elif self.input_file:
                # 从文件读取坐标数据
                self.progress_update.emit("Reading coordinates data...", 0)
                
                # 处理不同格式的文件
                file_ext = os.path.splitext(self.input_file)[1].lower()
                
                # 根据文件类型读取数据
                if file_ext == '.csv':
                    # 使用pandas读取CSV
                    self.progress_update.emit("Reading CSV file...", 5)
                    coordinates = self.read_csv_file(self.input_file)
                elif file_ext == '.txt':
                    # 读取文本文件
                    self.progress_update.emit("Reading text file...", 5)
                    coordinates = self.read_text_file(self.input_file)
                elif file_ext in ['.xlsx', '.xls']:
                    # 读取Excel文件
                    self.progress_update.emit("Reading Excel file...", 5)
                    coordinates = self.read_excel_file(self.input_file)
                else:
                    raise Exception(f"Unsupported file format: {file_ext}")
            else:
                raise Exception("No input data provided")
                
            # 验证坐标数据
            if not coordinates:
                raise Exception("No valid coordinates found in the input")
                
            self.progress_update.emit(f"Successfully read {len(coordinates)} points", 10)
            
            # 创建输出目录
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                self.progress_update.emit(f"Created output directory: {self.output_dir}", 10)
                
            # 计算总进度比例
            total_points = len(coordinates)
            points_processed = 0
            
            # 遍历处理每个坐标点
            for coord in coordinates:
                points_processed += 1
                point_progress_base = 10 + (points_processed - 1) * 90 / total_points
                
                name = coord['name']
                lat = coord['latitude']
                lng = coord['longitude']
                
                # 将站点名称转换为拼音/英文
                name_pinyin = self.to_pinyin(name)
                
                self.progress_update.emit(f"Processing point {points_processed}/{total_points}: {name}", point_progress_base)
                
                try:
                    # 生成等时圈
                    self.generate_isochrone(lat, lng, name, name_pinyin, point_progress_base)
                except Exception as e:
                    self.progress_update.emit(f"Error processing point {name}: {str(e)}", point_progress_base)
                    continue
            
            self.finished.emit(True, "All points processed successfully!")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")
            
    def to_pinyin(self, text):
        """将中文文本转换为拼音"""
        try:
            # 先尝试使用pypinyin转拼音
            pinyin = ''.join(lazy_pinyin(text))
            # 如果结果为空或与原文相同，使用简单的替换方法
            if not pinyin or pinyin == text:
                # 移除非ASCII字符
                ascii_text = re.sub(r'[^\x00-\x7F]+', '', text)
                return ascii_text.strip() if ascii_text.strip() else "Station"
            return pinyin
        except:
            # 出错时使用简单的替换方法
            ascii_text = re.sub(r'[^\x00-\x7F]+', '', text)
            return ascii_text.strip() if ascii_text.strip() else "Station"
            
    def generate_isochrone(self, lat, lng, name, name_pinyin, base_progress):
        """为单个坐标点生成等时圈"""
        # 步骤1: 数据准备 - 获取路网数据
        self.progress_update.emit(f"Step 1/4: Downloading network data for {name}...", base_progress + 5)
        # 获取距离范围内的步行路网，确保涵盖足够区域
        G = ox.graph_from_point((lat, lng), dist=4000, network_type='all')
        self.progress_update.emit(f"Network downloaded: {len(G.nodes)} nodes, {len(G.edges)} edges", base_progress + 10)
        
        # 步骤2: 路网分析 - 投影和构建网络
        self.progress_update.emit(f"Step 2/4: Building walking network...", base_progress + 15)
        # 将地理坐标投影到平面坐标系统(UTM)以便进行距离计算
        G_proj = ox.project_graph(G)
        
        # 创建起始点并投影到相同坐标系
        origin_point = Point(lng, lat)
        origin_gdf = gpd.GeoDataFrame(geometry=[origin_point], crs="EPSG:4326")
        origin_proj = origin_gdf.to_crs(G_proj.graph['crs'])
        origin_x, origin_y = origin_proj.geometry.x[0], origin_proj.geometry.y[0]
        
        # 找到路网中距离起始点最近的节点
        origin_node = ox.distance.nearest_nodes(G_proj, X=origin_x, Y=origin_y)
        
        # 设置每条边的权重为长度(米)，用于后续计算
        for u, v, data in G_proj.edges(data=True):
            data['weight'] = data['length']
        
        self.progress_update.emit(f"Walking network built", base_progress + 20)
        
        # 步骤3: 等时圈计算 - 生成指定距离步行范围
        self.progress_update.emit(f"Step 3/4: Calculating {self.distance}m walking range...", base_progress + 25)
        # 计算从起始节点出发，在给定距离内可达的子图
        subgraph = nx.ego_graph(G_proj, origin_node, radius=self.distance, distance='weight')
        
        # 提取子图中的节点和边
        nodes, edges = ox.graph_to_gdfs(subgraph)
        
        # 生成缓冲区和合并操作，创建等时圈轮廓
        node_buffers = nodes.buffer(15)  # 节点缓冲区
        
        # 为边创建缓冲区
        edge_lines = [LineString([Point(data.geometry.coords[0]), 
                                 Point(data.geometry.coords[-1])]) 
                     for _, data in edges.iterrows()]
        edge_buffers = gpd.GeoSeries(edge_lines).buffer(10)  # 边缓冲区
        
        # 合并所有缓冲区创建初始等时圈
        buffers = list(node_buffers) + list(edge_buffers)
        if buffers:
            isochrone_polygon = unary_union(buffers)
            
            # 平滑处理
            isochrone_polygon = isochrone_polygon.buffer(10).buffer(-5)
            
            # 应用Douglas-Peucker简化算法，公差为2米
            isochrone_polygon = isochrone_polygon.simplify(2, preserve_topology=True)
            
            # 移除等时圈内部的空洞，确保是一个完整的多边形
            if hasattr(isochrone_polygon, 'geoms'):
                # 处理MultiPolygon情况：取面积最大的多边形
                largest_polygon = max(isochrone_polygon.geoms, key=lambda p: p.area)
                # 仅保留外部环，去除内部孔洞
                isochrone_polygon = Polygon(largest_polygon.exterior)
            else:
                # 处理单个Polygon情况：直接去除内部孔洞
                isochrone_polygon = Polygon(isochrone_polygon.exterior)
        else:
            # 如果没有可达点，创建一个小范围圆形作为等时圈
            isochrone_polygon = origin_proj.geometry[0].buffer(50)
        
        self.progress_update.emit(f"Walking range calculated", base_progress + 35)
        
        # 创建等时圈GeoDataFrame（WGS84坐标系）
        isochrone_gdf = gpd.GeoDataFrame(geometry=[isochrone_polygon])
        isochrone_gdf.crs = G_proj.graph['crs']
        
        # 添加属性信息
        isochrone_gdf['name'] = name
        isochrone_gdf['lat'] = lat
        isochrone_gdf['lng'] = lng
        isochrone_gdf['distance'] = self.distance  # 步行范围
        
        # 保存为Shapefile格式
        shp_dir = os.path.join(self.output_dir, "shapefiles")
        if not os.path.exists(shp_dir):
            os.makedirs(shp_dir)
            self.progress_update.emit(f"Created Shapefile directory: {shp_dir}", base_progress + 40)
        
        # 转换为WGS84坐标系统(EPSG:4326)并保存为Shapefile
        isochrone_wgs84 = isochrone_gdf.to_crs(epsg=4326)
        shp_filename = os.path.join(shp_dir, f'{name_pinyin}_{self.distance}m_walking')
        isochrone_wgs84.to_file(shp_filename, driver='ESRI Shapefile', encoding='utf-8')
        self.progress_update.emit(f"Saved Shapefile: {shp_filename}.shp", base_progress + 45)
        
        # 步骤4: 可视化输出 - 生成地图并保存
        self.progress_update.emit(f"Step 4/4: Generating map output...", base_progress + 50)
        
        # 转换为Web Mercator (EPSG:3857)用于绘图
        isochrone_web_mercator = isochrone_gdf.to_crs(epsg=3857)
        edges_web_mercator = edges.to_crs(epsg=3857)
        origin_web_mercator = origin_gdf.to_crs(epsg=3857)
        
        # 创建图形和坐标轴
        fig, ax = plt.subplots(1, 1, figsize=(10, 10), dpi=300)
        
        # 获取起始点坐标
        center_x = origin_web_mercator.geometry.x[0]
        center_y = origin_web_mercator.geometry.y[0]
        
        # 设置固定的视图范围 (4km x 4km)
        half_width = 2000  # 2km半径，总共4km
        ax.set_xlim([center_x - half_width, center_x + half_width])
        ax.set_ylim([center_y - half_width, center_y + half_width])
        
        self.progress_update.emit(f"Setting up map canvas", base_progress + 60)
        
        # 添加底图 (OpenStreetMap)
        cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik, zoom=16)
        
        # 绘制路网
        edges_web_mercator.plot(ax=ax, linewidth=0.7, color='gray', alpha=0.6, zorder=2)
        
        # 仅绘制等时圈轮廓 - 蓝色(#0000FF)，宽度1px，无填充
        isochrone_web_mercator.boundary.plot(
            ax=ax, 
            color='#0000FF',  # 蓝色
            linewidth=1,      # 1像素宽度
            zorder=3          # 确保在路网上方显示
        )
        
        # 绘制起始点
        origin_web_mercator.plot(
            ax=ax, 
            color='red', 
            marker='*', 
            markersize=100, 
            zorder=4
        )
        
        self.progress_update.emit(f"Drawing map elements", base_progress + 70)
        
        # 添加比例尺
        ax.add_artist(ScaleBar(
            dx=1, 
            location='lower right', 
            box_alpha=0.5, 
            color='black'
        ))
        
        # 添加图例 - 使用英文标签
        legend_elements = [
            plt.Line2D([0], [0], color='#0000FF', lw=1, label=f'{self.distance}m Walking Range'),
            plt.Line2D([0], [0], color='gray', lw=0.7, alpha=0.6, label='Walking Network'),
            plt.Line2D([0], [0], color='red', marker='*', lw=0, markersize=10, label='Starting Point')
        ]
        ax.legend(handles=legend_elements, loc='lower left', framealpha=0.5)
        
        # 移除坐标轴
        ax.set_axis_off()
        
        # 添加标题 - 使用英文标题
        plt.title(f'{name_pinyin} - {self.distance}m Walking Isochrone', fontsize=14)
        plt.tight_layout()
        
        self.progress_update.emit(f"Finalizing map", base_progress + 80)
        
        # 保存为PNG格式
        output_filename = os.path.join(self.output_dir, f'{name_pinyin}_{self.distance}m_walking.png')
        plt.savefig(output_filename, dpi=300, bbox_inches='tight', format='png')
        plt.close()
        
        self.progress_update.emit(f"Saved map to: {output_filename}", base_progress + 85)
        return output_filename
            
    def read_csv_file(self, file_path):
        try:
            # 尝试使用pandas读取，假设有标题行
            df = pd.read_csv(file_path)
            
            # 检查是否包含必要的列
            if 'name' in df.columns and 'latitude' in df.columns and 'longitude' in df.columns:
                # 标准格式CSV
                return df[['name', 'latitude', 'longitude']].to_dict('records')
            else:
                # 尝试只读取数据，不假设列名
                coordinates = []
                df = pd.read_csv(file_path, header=None)
                
                # 如果仅有3列，假设为name,lng,lat格式
                if df.shape[1] == 3:
                    for _, row in df.iterrows():
                        coordinates.append({
                            'name': str(row[0]),
                            'longitude': float(row[1]),
                            'latitude': float(row[2])
                        })
                else:
                    # 直接尝试正则解析
                    return self.parse_text_content(open(file_path, 'r', encoding='utf-8').read())
                
                return coordinates
        except Exception as e:
            self.progress_update.emit(f"CSV parsing error: {str(e)}, trying text format", 5)
            # 如果CSV解析失败，回退到文本解析
            return self.read_text_file(file_path)
            
    def read_text_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return self.parse_text_content(content)
        except Exception as e:
            raise Exception(f"Failed to read text file: {str(e)}")
            
    def read_excel_file(self, file_path):
        try:
            # 尝试使用pandas读取Excel
            df = pd.read_excel(file_path)
            
            # 检查是否包含必要的列
            if 'name' in df.columns and 'latitude' in df.columns and 'longitude' in df.columns:
                # 标准格式
                return df[['name', 'latitude', 'longitude']].to_dict('records')
            else:
                # 尝试解析内容
                coordinates = []
                
                # 如果仅有3列，假设为name,lng,lat格式
                if df.shape[1] == 3:
                    for _, row in df.iterrows():
                        try:
                            coordinates.append({
                                'name': str(row[0]),
                                'longitude': float(row[1]),
                                'latitude': float(row[2])
                            })
                        except:
                            # 跳过无效行
                            pass
                
                # 如果无法按上述方式解析，尝试从每一行文本中提取
                if not coordinates:
                    text_content = ""
                    for _, row in df.iterrows():
                        for col in df.columns:
                            text_content += str(row[col]) + "\n"
                    coordinates = self.parse_text_content(text_content)
                
                return coordinates
        except Exception as e:
            raise Exception(f"Failed to read Excel file: {str(e)}")
            
    def parse_text_content(self, content):
        """从文本内容中解析坐标点"""
        coordinates = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 使用正则表达式匹配格式: 名称 (经度, 纬度) 或类似变体
            match = re.match(r'(.+?)\s*[\(\[\{]?\s*(\d+\.\d+)\s*,\s*(\d+\.\d+)\s*[\)\]\}]?', line)
            if match:
                name = match.group(1).strip()
                lng = float(match.group(2))
                lat = float(match.group(3))
                coordinates.append({
                    'name': name,
                    'longitude': lng,
                    'latitude': lat
                })
                continue
                
            # 尝试匹配Tab或逗号分隔的数据
            parts = re.split(r'[\t,]+', line)
            if len(parts) >= 3:
                try:
                    name = parts[0].strip()
                    # 尝试不同位置组合找出经纬度
                    for i in range(1, len(parts)-1):
                        try:
                            lng = float(parts[i])
                            lat = float(parts[i+1])
                            coordinates.append({
                                'name': name,
                                'longitude': lng,
                                'latitude': lat
                            })
                            break
                        except:
                            continue
                except:
                    pass
        
        return coordinates

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walking Isochrone Generator")
        self.setMinimumSize(1000, 800)
        self.init_ui()
        
    def init_ui(self):
        # 创建选项卡窗口部件
        self.tabs = QTabWidget()
        
        # 第一个选项卡：基于文件的处理
        self.file_tab = QWidget()
        self.setup_file_tab()
        
        # 第二个选项卡：基于地图选点的处理
        self.map_tab = QWidget()
        self.setup_map_tab()
        
        # 添加选项卡
        self.tabs.addTab(self.file_tab, "File-based Processing")
        self.tabs.addTab(self.map_tab, "Map Selection")
        
        # 设置为中央窗口部件
        self.setCentralWidget(self.tabs)
        
        # 设置菜单栏
        self.setup_menu()
        
        # 内部变量
        self.input_file = ""
        self.output_dir = "isochrone_output"
        self.worker = None
        
    def setup_file_tab(self):
        # 文件选项卡布局
        layout = QVBoxLayout(self.file_tab)
        
        # 输入区域
        input_group = QGroupBox("Input Settings")
        form_layout = QFormLayout()
        
        # 文件选择
        self.file_path_label = QLabel("No file selected")
        file_select_btn = QPushButton("Select File")
        file_select_btn.clicked.connect(self.select_file)
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(file_select_btn)
        form_layout.addRow("Coordinates:", file_layout)
        
        # 输出目录
        self.output_dir_label = QLabel("isochrone_output")
        output_dir_btn = QPushButton("Select Output Directory")
        output_dir_btn.clicked.connect(self.select_output_dir)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_label)
        output_layout.addWidget(output_dir_btn)
        form_layout.addRow("Output Directory:", output_layout)
        
        # 步行距离设置
        self.distance_spin = QSpinBox()
        self.distance_spin.setRange(500, 5000)
        self.distance_spin.setValue(1000)
        self.distance_spin.setSingleStep(100)
        self.distance_spin.setSuffix(" meters")
        form_layout.addRow("Walking Distance:", self.distance_spin)
        
        input_group.setLayout(form_layout)
        layout.addWidget(input_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Generate Isochrones")
        self.start_btn.clicked.connect(self.start_analysis)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)
        
        # 进度显示
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_text)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
    def setup_map_tab(self):
        # 地图选项卡布局
        layout = QVBoxLayout(self.map_tab)
        
        # 创建地图选点组件
        self.map_selector = MapSelector()
        
        # 连接信号
        self.map_selector.isochrone_requested.connect(self.start_map_based_analysis)
        
        # 添加到布局
        layout.addWidget(self.map_selector)
        
    def setup_menu(self):
        # 创建菜单栏
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('File')
        
        # 导入坐标点
        import_action = file_menu.addAction('Import Points...')
        import_action.triggered.connect(self.import_points)
        
        # 导出坐标点
        export_action = file_menu.addAction('Export Points...')
        export_action.triggered.connect(self.export_points)
        
        # 退出
        exit_action = file_menu.addAction('Exit')
        exit_action.triggered.connect(self.close)
        
        # 帮助菜单
        help_menu = menubar.addMenu('Help')
        
        # 关于
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)
        
    def import_points(self):
        """从文件导入坐标点到地图"""
        # 切换到地图选项卡
        self.tabs.setCurrentWidget(self.map_tab)
        # 调用地图选点组件的导入功能
        self.map_selector.import_points()
        
    def export_points(self):
        """导出地图上的坐标点到文件"""
        # 切换到地图选项卡
        self.tabs.setCurrentWidget(self.map_tab)
        # 调用地图选点组件的导出功能
        self.map_selector.export_points()
        
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "About Walking Isochrone Generator",
                          """<h3>Walking Isochrone Generator</h3>
                          <p>A tool for generating precise walking isochrones based on OpenStreetMap data.</p>
                          <p>Features:</p>
                          <ul>
                          <li>File-based processing of multiple coordinates</li>
                          <li>Interactive map selection of points</li>
                          <li>Support for multiple file formats</li>
                          <li>Precise isochrone calculation</li>
                          <li>High-quality map output</li>
                          </ul>""")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Coordinates File", 
            "", 
            "All Supported Files (*.csv *.txt *.xlsx *.xls);;CSV Files (*.csv);;Text Files (*.txt);;Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.input_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
    
    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir = dir_path
            self.output_dir_label.setText(dir_path)
            # 同时更新地图选项卡的输出目录
            self.map_selector.output_dir_edit.setText(dir_path)
    
    def start_analysis(self):
        """开始基于文件的等时圈生成"""
        if not self.input_file:
            QMessageBox.warning(self, "Warning", "Please select a coordinates file first!")
            return
            
        self.start_btn.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        distance = self.distance_spin.value()
        
        # 创建并启动工作线程
        self.worker = IsochroneWorker(self.input_file, self.output_dir, distance)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.analysis_finished)
        self.worker.start()
        
    def start_map_based_analysis(self, points_data, output_dir, distance):
        """开始基于地图选点的等时圈生成"""
        # 切换到文件选项卡，以显示进度
        self.tabs.setCurrentWidget(self.file_tab)
        
        self.start_btn.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # 创建并启动工作线程
        self.worker = IsochroneWorker(None, output_dir, distance, points_data)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.analysis_finished)
        self.worker.start()
        
    def update_progress(self, message, progress):
        self.log_text.append(message)
        self.progress_bar.setValue(progress)
    
    def analysis_finished(self, success, message):
        self.log_text.append(message)
        if success:
            QMessageBox.information(self, "Complete", "Isochrones generated successfully!")
        else:
            QMessageBox.critical(self, "Error", message)
        self.start_btn.setEnabled(True)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
