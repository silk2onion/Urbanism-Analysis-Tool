import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import geopandas as gpd
import contextily as cx
import numpy as np
from tqdm import tqdm
import pandas as pd
import os
import re
from matplotlib_scalebar.scalebar import ScaleBar
from pypinyin import lazy_pinyin

"""
步行等时圈生成工具

- 基于给定起始点计算1000米步行范围等时圈
- 考虑地理障碍物和实际步行路径
- 输出为PNG格式地图
"""

# 读取CSV文件中的起始点坐标
print("正在读取起始点坐标数据...")
try:
    # 读取文件内容
    with open('metrostation.CSV', 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # 解析数据
    stations_data = []
    for line in lines:
        line = line.strip()
        if not line:  # 跳过空行
            continue
            
        # 使用正则表达式匹配站点名称和坐标
        match = re.match(r'(.+?)\s*\((\d+\.\d+),\s*(\d+\.\d+)\)', line)
        if match:
            name = match.group(1).strip()
            lng = float(match.group(2))
            lat = float(match.group(3))
            stations_data.append({
                'name': name,
                'longitude': lng,
                'latitude': lat
            })
    
    # 创建DataFrame
    stations_df = pd.DataFrame(stations_data)
    
    if stations_df.empty:
        raise Exception("未找到有效的起始点坐标")
    
    # 显示数据预览
    print("\n数据预览:")
    print(stations_df.head())
    print(f"\n成功读取了 {len(stations_df)} 个起始点坐标")
    
except Exception as e:
    print(f"读取坐标文件出错: {e}")
    print("\n请确保坐标文件格式正确:")
    print("1. 每行格式应为: 站点名称 (经度, 纬度)")
    print("2. 例如: 团岛 (120.2945709, 36.057163)")
    exit(1)

# 创建输出目录
output_dir = "等时圈结果"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"创建输出目录: {output_dir}")

# 遍历每个起始点
for index, row in tqdm(stations_df.iterrows(), total=len(stations_df), desc="处理起始点"):
    lat = row['latitude']
    lng = row['longitude']
    station_name = row['name'] if 'name' in row else f"点位_{index+1}"

    # 将站点名称转换为拼音
    station_name_pinyin = ''.join(lazy_pinyin(station_name))

    print(f"\n处理起始点: {station_name} (拼音: {station_name_pinyin}) (纬度: {lat}, 经度: {lng})")

    try:
        # 步骤1: 数据准备 - 获取路网数据
        print("步骤1/4: 获取路网数据...")
        with tqdm(total=100, desc="下载进度") as pbar:
            # 获取4公里范围内的步行路网，确保涵盖足够区域
            G = ox.graph_from_point((lat, lng), dist=4000, network_type='all')
            pbar.update(100)

        # 步骤2: 路网分析 - 投影和构建网络
        print("步骤2/4: 构建步行路网...")
        with tqdm(total=100, desc="处理进度") as pbar:
            # 将地理坐标投影到平面坐标系统(UTM)以便进行距离计算
            G_proj = ox.project_graph(G)
            pbar.update(33)
            
            # 创建起始点并投影到相同坐标系
            origin_point = Point(lng, lat)
            origin_gdf = gpd.GeoDataFrame(geometry=[origin_point], crs="EPSG:4326")
            origin_proj = origin_gdf.to_crs(G_proj.graph['crs'])
            origin_x, origin_y = origin_proj.geometry.x[0], origin_proj.geometry.y[0]
            
            # 找到路网中距离起始点最近的节点
            origin_node = ox.distance.nearest_nodes(G_proj, X=origin_x, Y=origin_y)
            pbar.update(33)
            
            # 设置每条边的权重为长度(米)，用于后续计算
            for u, v, data in G_proj.edges(data=True):
                data['weight'] = data['length']
            pbar.update(34)

        # 步骤3: 等时圈计算 - 生成1000米步行范围
        print("步骤3/4: 计算步行范围...")
        with tqdm(total=100, desc="计算进度") as pbar:
            # 计算从起始节点出发，在给定距离(1000米)内可达的子图
            # 使用weight属性作为边权重，即长度
            subgraph = nx.ego_graph(G_proj, origin_node, radius=1000, distance='weight')
            pbar.update(25)
            
            # 提取子图中的节点和边
            nodes, edges = ox.graph_to_gdfs(subgraph)
            pbar.update(25)
            
            # 生成缓冲区和合并操作，创建等时圈轮廓
            node_buffers = nodes.buffer(20)  # 增加节点缓冲区
            
            # 为边创建缓冲区
            edge_lines = [LineString([Point(data.geometry.coords[0]), 
                                     Point(data.geometry.coords[-1])]) 
                         for _, data in edges.iterrows()]
            edge_buffers = gpd.GeoSeries(edge_lines).buffer(15)  # 增加边缓冲区
            pbar.update(25)
            
            # 合并所有缓冲区创建初始等时圈
            buffers = list(node_buffers) + list(edge_buffers)
            if buffers:
                isochrone_polygon = unary_union(buffers)
                
                # 平滑处理
                isochrone_polygon = isochrone_polygon.buffer(10).buffer(-5)
                
                # 应用Douglas-Peucker简化算法，公差为20米
                isochrone_polygon = isochrone_polygon.simplify(20, preserve_topology=True)
                
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
            pbar.update(25)

            node_buffers.plot()
            edge_buffers.plot()

        # 步骤4: 可视化输出 - 生成地图并保存
        print("步骤4/4: 生成地图输出...")
        with tqdm(total=100, desc="可视化进度") as pbar:
            # 创建等时圈GeoDataFrame
            isochrone_gdf = gpd.GeoDataFrame(geometry=[isochrone_polygon])
            isochrone_gdf.crs = G_proj.graph['crs']
            
            # 转换为Web Mercator (EPSG:3857)用于绘图
            isochrone_web_mercator = isochrone_gdf.to_crs(epsg=3857)
            edges_web_mercator = edges.to_crs(epsg=3857)
            origin_web_mercator = origin_gdf.to_crs(epsg=3857)
            pbar.update(20)
            
            # 创建图形和坐标轴
            fig, ax = plt.subplots(1, 1, figsize=(10, 10))
            
            # 获取起始点坐标
            center_x = origin_web_mercator.geometry.x[0]
            center_y = origin_web_mercator.geometry.y[0]
            
            # 设置固定的视图范围 (4km x 4km)
            half_width = 2000  # 2km半径，总共4km
            ax.set_xlim([center_x - half_width, center_x + half_width])
            ax.set_ylim([center_y - half_width, center_y + half_width])
            pbar.update(20)
            
            # 添加底图 (OpenStreetMap) 并设置缩放等级
            cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik, zoom=16)
            
            # 绘制路网
            edges_web_mercator.plot(ax=ax, linewidth=0.7, color='gray', alpha=0.6, zorder=2)
            
            # 绘制等时圈轮廓 - 蓝色(#0000FF)，宽度1px，无填充
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
            pbar.update(20)
            
            # 添加比例尺
            ax.add_artist(ScaleBar(
                dx=1, 
                location='lower right', 
                box_alpha=0.5, 
                color='black'
            ))
            
            # 添加图例
            legend_elements = [
                plt.Line2D([0], [0], color='#0000FF', lw=1, label='1000m Walking Range'),
                plt.Line2D([0], [0], color='gray', lw=0.7, alpha=0.6, label='Walking Network'),
                plt.Line2D([0], [0], color='red', marker='*', lw=0, markersize=10, label='Origin Point')
            ]
            ax.legend(handles=legend_elements, loc='lower left', framealpha=0.5)
            
            # 移除坐标轴
            ax.set_axis_off()
            
            # 添加标题
            plt.title(f'{station_name_pinyin} - 1000m Walking Isochrone', fontsize=14)
            plt.tight_layout()
            
            # 保存为PNG格式
            output_filename = os.path.join(output_dir, f'{station_name_pinyin}_1000m_Walking_Isochrone.png')
            plt.savefig(output_filename, dpi=300, bbox_inches='tight', format='png')
            plt.close()
            pbar.update(20)
            
            print(f"Saved map to: {output_filename}")
            
        print(f"已保存地图到: {output_filename}")
        
    except Exception as e:
        print(f"处理起始点 {station_name} 时出错: {e}")
        print(f"错误详情: {str(e)}")
        continue

print("\n所有起始点处理完成！")