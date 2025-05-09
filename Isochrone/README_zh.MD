# 🚶‍♂️ 步行等时圈生成工具 🗺️

## ✨ 功能介绍
这是一个超级实用的工具，帮你轻松生成步行等时圈地图！不用担心复杂计算，只需提供起始点坐标，它就能：
- 🏃‍♀️ 基于给定起始点计算1000米步行范围等时圈
- 🧭 智能考虑地理障碍物和实际步行路径
- 🖼️ 输出为高质量PNG格式地图

## 📋 使用前准备

### 必要的库
使用前请确保安装了这些Python库（小伙伴们可以用pip一键搞定）：
```bash
pip install osmnx networkx matplotlib shapely geopandas contextily numpy tqdm pandas pypinyin matplotlib-scalebar
```

### 输入数据格式
准备一个名为 `metrostation.CSV` 的文件，每行格式为：
```csv
站点名称 (经度, 纬度)
```
例如：
```csv
团岛 (120.2945709, 36.057163)
```

## 🚀 使用方法
1. 把你的 `metrostation.CSV` 文件放在程序同目录下。
2. 运行程序：
    ```bash
    python main.py
    ```
   然后就可以坐等结果啦~程序会显示处理进度和详细信息。

## 🔍 工作原理
这个工具的魔法是这样实现的：
- 📥 数据准备: 获取起始点周围4km范围的路网数据
- 🌐 路网分析: 投影坐标并构建网络模型
- ⏱️ 等时圈计算: 生成1000米步行可达范围
- 🎨 可视化输出: 生成漂亮的地图并保存为PNG

## 📂 输出结果
所有生成的地图都会保存在等时圈结果文件夹中，文件名格式为：
```plaintext
站点名称拼音_1000m_Walking_Isochrone.png
```

## 🌟 特色功能
- 🔄 批量处理多个起始点
- 🧩 自动处理并简化等时圈轮廓
- 🗺️ 集成OpenStreetMap底图
- 📏 自动添加比例尺和图例
- 🌈 美观的可视化效果

## 🛠️ 小贴士
- 如果遇到坐标文件读取错误，请检查文件格式是否正确。
- 程序会自动将中文站点名转换为拼音用于文件命名。
- 默认生成的等时圈为蓝色线条，起始点为红色星标。

快去试试吧！有任何问题或建议都欢迎反馈~ 😊
