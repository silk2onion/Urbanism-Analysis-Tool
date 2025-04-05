import sys
import os
import folium
import tempfile
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QTabWidget, QStatusBar, QPushButton,
                            QLabel, QLineEdit, QMessageBox, QFileDialog,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QSpinBox, QGroupBox, QFormLayout, QDialogButtonBox,
                            QDialog, QComboBox, QSplitter)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, pyqtSlot, QUrl, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from folium.plugins import Draw, MousePosition

class PointInfo:
    """管理单个选点的信息"""
    def __init__(self, name="", lat=0, lng=0):
        self.name = name
        self.lat = lat
        self.lng = lng
        
    def __str__(self):
        return f"{self.name}: ({self.lat:.6f}, {self.lng:.6f})"
        
    def to_dict(self):
        return {"name": self.name, "latitude": self.lat, "longitude": self.lng}

class PyHandler(QObject):
    """JavaScript与Python之间的桥接处理器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.map_selector = parent
        
    @pyqtSlot(float, float)
    def handlePointSelected(self, lat, lng):
        if self.map_selector:
            self.map_selector.on_map_point_selected(lat, lng)
            
    @pyqtSlot(float, float)
    def handlePointConfirmed(self, lat, lng):
        if self.map_selector:
            self.map_selector.on_point_confirmed(lat, lng)
            
    @pyqtSlot()
    def cancelSelection(self):
        if self.map_selector:
            self.map_selector.exit_selection_mode()

class MapSelector(QWidget):
    """交互式地图选点组件"""
    # 自定义信号
    point_selected = pyqtSignal(float, float)
    isochrone_requested = pyqtSignal(list, str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_points = []
        self.selection_mode_active = False
        self.temp_point = None
        self.temp_html = None
        self.map_view = None
        self.points_table = None
        
        # 主布局 - 在setup_ui里面设置
        self.main_layout = None
        self.setup_ui()
        
    def setup_ui(self):
        # 创建主布局
        self.main_layout = QVBoxLayout()
        
        # 创建地图区域
        self.map_widget = QWidget()
        map_layout = QVBoxLayout()
        
        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search for a location...")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_location)
        
        # 地图类型选择
        self.map_type_combo = QComboBox()
        self.map_type_combo.addItem("OpenStreetMap")
        self.map_type_combo.addItem("Stamen Terrain")
        self.map_type_combo.addItem("Stamen Toner")
        self.map_type_combo.addItem("CartoDB Positron")
        self.map_type_combo.currentIndexChanged.connect(self.change_map_type)
        
        search_layout.addWidget(QLabel("Map Type:"))
        search_layout.addWidget(self.map_type_combo)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.search_btn)
        
        map_layout.addLayout(search_layout)
        
        # 创建地图视图
        self.map_view = QWebEngineView()
        map_layout.addWidget(self.map_view)
        
        self.map_widget.setLayout(map_layout)
        
        # 点位列表区域
        self.points_widget = QWidget()
        points_layout = QVBoxLayout()
        
        # 创建表格显示点位
        self.points_table = QTableWidget(0, 3)
        self.points_table.setHorizontalHeaderLabels(["Name", "Latitude", "Longitude"])
        self.points_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        points_layout.addWidget(QLabel("Selected Points:"))
        points_layout.addWidget(self.points_table)
        
        # 点位操作按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Point From Map")
        self.add_btn.clicked.connect(self.start_map_selection_mode)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self.edit_selected_point)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove_selected_point)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all_points)
        
        # 添加手动输入按钮
        self.add_manual_btn = QPushButton("Add Point Manually")
        self.add_manual_btn.clicked.connect(self.add_point_manually)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.add_manual_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        points_layout.addLayout(btn_layout)
        
        # 等时圈设置区域
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Walking Distance:"))
        self.distance_spin = QSpinBox()
        self.distance_spin.setRange(500, 5000)
        self.distance_spin.setValue(1000)
        self.distance_spin.setSingleStep(100)
        self.distance_spin.setSuffix(" meters")
        settings_layout.addWidget(self.distance_spin)
        
        settings_layout.addWidget(QLabel("Output Directory:"))
        self.output_dir_edit = QLineEdit("isochrone_output")
        settings_layout.addWidget(self.output_dir_edit)
        
        points_layout.addLayout(settings_layout)
        
        # 生成等时圈按钮
        self.generate_btn = QPushButton("Generate Isochrones for Selected Points")
        self.generate_btn.clicked.connect(self.generate_isochrones)
        points_layout.addWidget(self.generate_btn)
        
        self.points_widget.setLayout(points_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(self.points_widget)
        splitter.setSizes([600, 300])  # 初始分割比例
        
        self.main_layout.addWidget(splitter)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.status_label = QLabel("")
        self.status_bar.addWidget(self.status_label)
        
        # 取消选择按钮
        self.cancel_selection_btn = QPushButton("Cancel Selection")
        self.cancel_selection_btn.clicked.connect(self.exit_selection_mode)
        self.cancel_selection_btn.setVisible(False)
        self.status_bar.addPermanentWidget(self.cancel_selection_btn)
        
        # 确认点位按钮
        self.confirm_point_btn = QPushButton("Confirm Point")
        self.confirm_point_btn.clicked.connect(self.confirm_current_point)
        self.confirm_point_btn.setVisible(False)
        self.confirm_point_btn.setEnabled(False)
        self.status_bar.addPermanentWidget(self.confirm_point_btn)
        
        self.main_layout.addWidget(self.status_bar)
        
        # 设置主布局
        self.setLayout(self.main_layout)
        
        # 初始化地图
        self.init_map()

    def init_map(self, center=(39.9042, 116.4074), zoom=10):
        """初始化folium地图"""
        # 创建folium地图
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles="OpenStreetMap"
        )
        
        # 添加鼠标位置显示
        MousePosition().add_to(m)
        
        # 添加绘制工具
        draw = Draw(
            draw_options={
                'polyline': False,
                'rectangle': False,
                'polygon': False,
                'circle': False,
                'marker': True,
                'circlemarker': False
            },
            edit_options={
                'edit': False,
                'remove': True
            }
        )
        draw.add_to(m)
        
        # 添加点击事件
        m.add_child(folium.LatLngPopup())
        
        # 保存为临时文件并显示
        self.temp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False).name
        m.save(self.temp_html)
        
        # 在Qt WebView中显示地图
        self.map_view.load(QUrl.fromLocalFile(self.temp_html))
        
        # 等待页面加载完成后再添加事件监听
        self.map_view.loadFinished.connect(self.on_map_load_finished)

    def on_map_load_finished(self, ok):
        """地图加载完成后的回调"""
        if not ok:
            QMessageBox.warning(self, "Error", "Failed to load the map")
            return
        
        # 等待一段时间确保地图完全初始化
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, self.setup_map_interactions)
        
    def setup_map_interactions(self):
        """设置地图交互"""
        # 添加JavaScript与Python交互的WebChannel
        self.web_channel = QWebChannel(self.map_view.page())
        self.handler = PyHandler(self)
        self.web_channel.registerObject("pyHandler", self.handler)
        self.map_view.page().setWebChannel(self.web_channel)
        
        # 注入JavaScript代码以处理地图事件
        self.map_view.page().runJavaScript("""
        try {
            // 确保Leaflet已加载且地图已初始化
            if (typeof L !== 'undefined' && document.readyState === 'complete') {
                // 获取地图实例
                var mapInstance = null;
                // 尝试找到Leaflet地图实例
                for (var i in window) {
                    if (window[i] && window[i].hasOwnProperty && 
                        window[i].hasOwnProperty('_leaflet_id') && 
                        window[i]._leaflet) {
                        mapInstance = window[i];
                        break;
                    }
                }
                
                if (!mapInstance) {
                    console.error('Cannot find Leaflet map instance');
                    return;
                }
                
                // 保存地图实例到全局变量，供其他函数使用
                window.map = mapInstance;
                window.selectionModeActive = false;
                
                // 临时标记对象
                window.tempMarker = null;
                
                // 创建bridge对象用于PyQt通信
                window.pyqtBridge = {
                    pointSelected: function(lat, lng) {
                        console.log('Point selected:', lat, lng);
                        
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            var pyHandler = channel.objects.pyHandler;
                            if (pyHandler) {
                                pyHandler.handlePointSelected(lat, lng);
                            } else {
                                console.error("Python handler not found");
                            }
                        });
                    },
                    confirmPoint: function(lat, lng) {
                        console.log('Point confirmed:', lat, lng);
                        
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            var pyHandler = channel.objects.pyHandler;
                            if (pyHandler) {
                                pyHandler.handlePointConfirmed(lat, lng);
                            }
                        });
                    }
                };
                
                // 地图点击事件
                mapInstance.on('click', function(e) {
                    if (!window.selectionModeActive) {
                        return;
                    }
                    
                    var lat = e.latlng.lat;
                    var lng = e.latlng.lng;
                    console.log('Map clicked at:', lat, lng);
                    
                    // 移除之前的临时标记
                    if (window.tempMarker) {
                        mapInstance.removeLayer(window.tempMarker);
                    }
                    
                    // 创建新的临时标记
                    window.tempMarker = L.marker([lat, lng], {
                        draggable: true,  // 可拖动
                        icon: L.icon({
                            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41],
                            popupAnchor: [1, -34]
                        })
                    }).addTo(mapInstance);
                    
                    // 绑定拖动结束事件，更新坐标
                    window.tempMarker.on('dragend', function(event) {
                        var marker = event.target;
                        var position = marker.getLatLng();
                        // 更新坐标
                        window.pyqtBridge.pointSelected(position.lat, position.lng);
                    });
                    
                    // 创建确认按钮的HTML内容
                    var confirmBtnHtml = '<div style="display:flex;align-items:center;margin-top:5px;">' +
                        '<span style="margin-right:10px;">' + lat.toFixed(6) + ', ' + lng.toFixed(6) + '</span>' +
                        '<button onclick="window.pyqtBridge.confirmPoint(' + lat + ', ' + lng + ')" ' +
                        'style="background-color:#4CAF50;color:white;border:none;border-radius:50%;' +
                        'width:24px;height:24px;font-weight:bold;cursor:pointer;display:flex;' +
                        'align-items:center;justify-content:center;margin-left:5px;">✓</button>' +
                        '</div>';
                    
                    // 绑定弹出窗口
                    window.tempMarker.bindPopup(confirmBtnHtml).openPopup();
                    
                    // 通知Python更新坐标
                    window.pyqtBridge.pointSelected(lat, lng);
                });
                
                // 右键点击取消选点
                mapInstance.on('contextmenu', function(e) {
                    if (window.selectionModeActive) {
                        // 通知Python退出选点模式
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            var pyHandler = channel.objects.pyHandler;
                            if (pyHandler) {
                                pyHandler.cancelSelection();
                            }
                        });
                    }
                });
                
                console.log('Map interactions setup completed');
            } else {
                console.error('Leaflet not loaded or page not ready');
            }
        } catch (error) {
            console.error('Error setting up map interactions:', error);
        }
        """)
        
        # 加载已有的点
        for point in self.selected_points:
            self.add_marker_to_map(point.lat, point.lng, point.name)

    def search_location(self):
        """搜索地点并在地图上标记"""
        query = self.search_edit.text().strip()
        if not query:
            return
        
        try:
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="isochrone_generator")
            location = geolocator.geocode(query)
            
            if location:
                # 转义查询字符串中的引号，避免JavaScript错误
                query_escaped = query.replace('"', '\\"').replace("'", "\\'")
                
                # 移动地图到搜索位置
                self.map_view.page().runJavaScript(f"""
                if (window.map) {{
                    window.map.setView([{location.latitude}, {location.longitude}], 14);
                    
                    // 添加临时标记
                    if (window.searchMarker) {{
                        window.map.removeLayer(window.searchMarker);
                    }}
                    window.searchMarker = L.marker([{location.latitude}, {location.longitude}]).addTo(window.map);
                    window.searchMarker.bindPopup("{query_escaped}<br>{location.latitude:.6f}, {location.longitude:.6f}<br><button class='add-search-point'>Add This Point</button>").openPopup();
                    
                    // 设置添加点按钮事件
                    setTimeout(function() {{
                        var addBtn = document.querySelector('.add-search-point');
                        if (addBtn) {{
                            addBtn.addEventListener('click', function() {{
                                window.pyqtBridge.confirmPoint({location.latitude}, {location.longitude});
                            }});
                        }}
                    }}, 100);
                }}
                """)
            else:
                QMessageBox.warning(self, "Location Not Found", f"Could not find location: {query}")
        except Exception as e:
            QMessageBox.warning(self, "Search Error", f"Error searching: {str(e)}")

    def change_map_type(self):
        """更改地图类型"""
        map_type = self.map_type_combo.currentText()
        tiles = "OpenStreetMap"
        
        if map_type == "Stamen Terrain":
            tiles = "Stamen Terrain"
        elif map_type == "Stamen Toner":
            tiles = "Stamen Toner"
        elif map_type == "CartoDB Positron":
            tiles = "CartoDB Positron"
        
        # 刷新地图
        self.map_view.page().runJavaScript(f"""
        if (window.map) {{
            var center = window.map.getCenter();
            var zoom = window.map.getZoom();
            
            // 传递回Python重新初始化地图
            window.pyqtBridge.updateMapSettings(center.lat, center.lng, zoom, "{tiles}");
        }}
        """)

    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        if self.selection_mode_active:
            if event.key() == Qt.Key_Escape:
                # ESC键退出选点模式
                self.exit_selection_mode()
            elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # 回车键确认当前点
                self.confirm_current_point()
        
        # 调用父类方法处理其他键盘事件
        super().keyPressEvent(event)

    def on_map_point_selected(self, lat, lng):
        """处理地图上选择的点（仅选择坐标，不立即打开对话框）"""
        # 如果不是在选点模式，忽略点击事件
        if not self.selection_mode_active:
            return
        
        # 更新状态栏显示当前选择的坐标
        self.status_label.setText(f"Selected point: {lat:.6f}, {lng:.6f} (Click 'Confirm Point' or press Enter to add)")
        
        # 保存临时坐标点
        self.temp_point = (lat, lng)
        
        # 启用确认按钮
        self.confirm_point_btn.setEnabled(True)
        
        # 发出信号通知其他组件
        self.point_selected.emit(lat, lng)
    
    def on_point_confirmed(self, lat, lng):
        """处理确认按钮点击事件，打开编辑对话框"""
        # 如果不是在选点模式，忽略点击事件
        if not self.selection_mode_active:
            return
        
        # 打开编辑对话框 - 设置经纬度为只读
        from edit_point_dialog import EditPointDialog
        point = PointInfo(f"Point {len(self.selected_points)+1}", lat, lng)
        dialog = EditPointDialog(point, self, coordinates_readonly=True)
        
        # 退出选点模式
        self.exit_selection_mode()
        
        if dialog.exec_() == QDialog.Accepted:
            point = dialog.get_point()
            self.add_point_to_list(point)
            self.add_marker_to_map(point.lat, point.lng, point.name)
    
    def confirm_current_point(self):
        """确认当前选择的点位"""
        if self.temp_point:
            lat, lng = self.temp_point
            self.on_point_confirmed(lat, lng)
    
    def start_map_selection_mode(self):
        """开始地图选点模式"""
        self.selection_mode_active = True
        self.status_label.setText("Click on the map to select a location (Press ESC or right-click to cancel)")
        self.status_label.setVisible(True)
        self.cancel_selection_btn.setVisible(True)
        self.confirm_point_btn.setVisible(True)
        self.confirm_point_btn.setEnabled(False)  # 初始时禁用
        self.add_btn.setEnabled(False)
        self.map_view.setFocus()
        
        # 清除临时点位
        self.temp_point = None
        
        # 通知JavaScript启用选点模式
        self.map_view.page().runJavaScript("""
        if (window.map) {
            window.selectionModeActive = true;
            document.body.style.cursor = 'crosshair';
            
            // 移除现有临时标记
            if (window.tempMarker) {
                window.map.removeLayer(window.tempMarker);
                window.tempMarker = null;
            }
            
            console.log('Selection mode activated');
        }
        """)
        
        # 提示用户操作方法
        QMessageBox.information(self, "Map Selection Mode", 
                               "Click on the map to place a marker.\n"
                               "You can drag the marker to adjust its position.\n"
                               "Press 'Confirm Point' button when ready.\n"
                               "Press ESC or right-click to cancel.")
    
    def exit_selection_mode(self):
        """退出地图选点模式"""
        self.selection_mode_active = False
        self.status_label.setVisible(False)
        self.cancel_selection_btn.setVisible(False)
        self.confirm_point_btn.setVisible(False)
        self.confirm_point_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        
        # 清除临时点位
        self.temp_point = None
        
        # 通知JavaScript禁用选点模式并移除临时标记
        self.map_view.page().runJavaScript("""
        if (window.map) {
            window.selectionModeActive = false;
            document.body.style.cursor = '';
            
            // 移除临时标记
            if (window.tempMarker) {
                window.map.removeLayer(window.tempMarker);
                window.tempMarker = null;
            }
            
            console.log('Selection mode deactivated');
        }
        """)
    
    def add_point_manually(self):
        """手动添加点位"""
        # 此处需要创建EditPointDialog类
        from edit_point_dialog import EditPointDialog
        dialog = EditPointDialog(PointInfo(), self, coordinates_readonly=False)
        if dialog.exec_() == QDialog.Accepted:
            point = dialog.get_point()
            self.add_point_to_list(point)
            self.add_marker_to_map(point.lat, point.lng, point.name)
    
    def edit_selected_point(self):
        """编辑选中的点位"""
        current_row = self.points_table.currentRow()
        if current_row >= 0 and current_row < len(self.selected_points):
            from edit_point_dialog import EditPointDialog
            point = self.selected_points[current_row]
            dialog = EditPointDialog(point, self, coordinates_readonly=False)
            
            if dialog.exec_() == QDialog.Accepted:
                updated_point = dialog.get_point()
                self.selected_points[current_row] = updated_point
                
                # 更新表格
                self.points_table.setItem(current_row, 0, QTableWidgetItem(updated_point.name))
                self.points_table.setItem(current_row, 1, QTableWidgetItem(f"{updated_point.lat:.6f}"))
                self.points_table.setItem(current_row, 2, QTableWidgetItem(f"{updated_point.lng:.6f}"))
                
                # 刷新地图
                self.refresh_map()
        else:
            QMessageBox.warning(self, "No Selection", "Please select a point to edit")
    
    def remove_selected_point(self):
        """移除选中的点位"""
        current_row = self.points_table.currentRow()
        if current_row >= 0 and current_row < len(self.selected_points):
            self.selected_points.pop(current_row)
            self.points_table.removeRow(current_row)
            
            # 刷新地图
            self.refresh_map()
        else:
            QMessageBox.warning(self, "No Selection", "Please select a point to remove")
    
    def clear_all_points(self):
        """清空所有点位"""
        if not self.selected_points:
            return
            
        reply = QMessageBox.question(self, "Clear All Points", 
                                    "Are you sure you want to remove all points?",
                                    QMessageBox.Yes | QMessageBox.No, 
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.selected_points.clear()
            self.points_table.setRowCount(0)
            self.refresh_map()
    
    def refresh_map(self):
        """刷新地图，重新显示所有标记"""
        # 获取当前中心点和缩放级别
        map_type = self.map_type_combo.currentText()
        self.map_view.page().runJavaScript("""
        if (window.map) {
            var center = window.map.getCenter();
            var zoom = window.map.getZoom();
            return [center.lat, center.lng, zoom];
        } else {
            return [39.9042, 116.4074, 10];  // 默认值
        }
        """, self._refresh_map)
    
    def _refresh_map(self, result):
        """地图刷新回调"""
        try:
            center_lat, center_lng, zoom = result
            
            # 重新初始化地图
            self.init_map((center_lat, center_lng), zoom)
            
        except Exception as e:
            print(f"Error refreshing map: {str(e)}")
            self.init_map()  # 出错时使用默认值
    
    def add_marker_to_map(self, lat, lng, title):
        """在地图上添加标记"""
        title_escaped = title.replace('"', '\\"').replace("'", "\\'")  # 转义引号
        
        js_code = f"""
        if (window.map) {{
            var marker = L.marker([{lat}, {lng}], {{
                title: "{title_escaped}"
            }}).addTo(window.map);
            marker.bindPopup("{title_escaped}<br>{lat:.6f}, {lng:.6f}");
        }} else {{
            console.error("Map not initialized yet");
        }}
        """
        self.map_view.page().runJavaScript(js_code)
    
    def add_point_to_list(self, point):
        """将点添加到列表"""
        self.selected_points.append(point)
        
        # 更新表格
        row = self.points_table.rowCount()
        self.points_table.insertRow(row)
        self.points_table.setItem(row, 0, QTableWidgetItem(point.name))
        self.points_table.setItem(row, 1, QTableWidgetItem(f"{point.lat:.6f}"))
        self.points_table.setItem(row, 2, QTableWidgetItem(f"{point.lng:.6f}"))
    
    def export_points(self):
        """导出点位到CSV文件"""
        if not self.selected_points:
            QMessageBox.warning(self, "No Points", "No points to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Points", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                df = pd.DataFrame([p.to_dict() for p in self.selected_points])
                df.to_csv(file_path, index=False)
                QMessageBox.information(self, "Export Successful", 
                                      f"Exported {len(self.selected_points)} points to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export: {str(e)}")

    def import_points(self):
        """从CSV文件导入点位"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Points", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                df = pd.read_csv(file_path)
                
                # 清空现有点位
                reply = QMessageBox.question(self, "Import Points",
                    "Do you want to replace existing points or add to them?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes)
                    
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:  # 替换
                    self.selected_points.clear()
                    self.points_table.setRowCount(0)
                
                # 添加导入的点位
                for _, row in df.iterrows():
                    point = PointInfo(
                        name=str(row.get('name', f"Point {len(self.selected_points)+1}")),
                        lat=float(row['latitude']),
                        lng=float(row['longitude'])
                    )
                    self.add_point_to_list(point)
                
                # 刷新地图
                self.refresh_map()
                QMessageBox.information(self, "Import Successful", 
                                      f"Imported {len(df)} points from {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to import: {str(e)}")
    
    def generate_isochrones(self):
        """生成等时圈"""
        if not self.selected_points:
            QMessageBox.warning(self, "No Points", "Please select at least one point to generate isochrones")
            return
            
        # 获取设置
        distance = self.distance_spin.value()
        output_dir = self.output_dir_edit.text().strip()
        
        if not output_dir:
            output_dir = "isochrone_output"
            
        # 转换点列表为字典列表
        points_data = [point.to_dict() for point in self.selected_points]
        
        # 发出信号，由主窗口处理生成等时圈
        self.isochrone_requested.emit(points_data, output_dir, distance)

# 创建EditPointDialog类用于编辑点信息
class EditPointDialog(QDialog):
    """编辑点位信息的对话框"""
    def __init__(self, point=None, parent=None, coordinates_readonly=False):
        super().__init__(parent)
        self.setWindowTitle("Edit Point Information")
        self.point = point or PointInfo()
        self.coordinates_readonly = coordinates_readonly
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 点位名称
        self.name_edit = QLineEdit(self.point.name)
        self.name_edit.setFocus()  # 自动聚焦到名称字段
        form_layout.addRow("Name:", self.name_edit)
        
        # 纬度
        self.lat_edit = QLineEdit(str(self.point.lat))
        if self.coordinates_readonly:
            self.lat_edit.setReadOnly(True)
            self.lat_edit.setStyleSheet("background-color: #f0f0f0;")  # 设置只读状态的背景色
        form_layout.addRow("Latitude:", self.lat_edit)
        
        # 经度
        self.lng_edit = QLineEdit(str(self.point.lng))
        if self.coordinates_readonly:
            self.lng_edit.setReadOnly(True)
            self.lng_edit.setStyleSheet("background-color: #f0f0f0;")  # 设置只读状态的背景色
        form_layout.addRow("Longitude:", self.lng_edit)
        
        layout.addLayout(form_layout)
        
        # 添加提示信息
        if self.coordinates_readonly:
            info_label = QLabel("Coordinates are automatically filled from the map position.")
            info_label.setStyleSheet("color: #666666; font-style: italic;")
            layout.addWidget(info_label)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def accept(self):
        # 验证输入
        try:
            name = self.name_edit.text().strip()
            lat = float(self.lat_edit.text())
            lng = float(self.lng_edit.text())
            
            if not name:
                raise ValueError("Name cannot be empty")
            
            if not (-90 <= lat <= 90):
                raise ValueError("Latitude must be between -90 and 90")
                
            if not (-180 <= lng <= 180):
                raise ValueError("Longitude must be between -180 and 180")
                
            self.point.name = name
            self.point.lat = lat
            self.point.lng = lng
            super().accept()
            
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
        
    def get_point(self):
        return self.point
