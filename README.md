# Urbanism Analysis Tool

Welcome to the Urbanism Analysis Tool project! This project is a collection of practical tools designed for urban design and urbanism research. As a professional focused on urbanism and Transit-Oriented Development (TOD) research, I will continuously upload and update various useful analysis tools in this repository.

## 🏙️ Project Overview

This project aims to provide a series of tools to help urban designers, planners, and researchers conduct efficient urban analysis and design work. The tools currently developed and under development include:

### Existing Tools

- **Walking Isochrone Generation Tool** 🚶‍♂️
  - Generates a 1000-meter walking isochrone based on the given coordinates.
  - Intelligently considers geographical obstacles and actual walking paths.
  - Outputs high-quality PNG format maps.

### Tools Under Development

- **Space Syntax N-step (Point-depth) Analysis Tool** 🔄
  - Development progress: 30%
  - This tool will be used for space syntax analysis to help understand urban spatial structure and accessibility.

## 📋 Prerequisites

### Environment Requirements

- Python 3.8+
- Supported Operating Systems: Windows/macOS/Linux

### Required Libraries

Make sure to install the following Python libraries before using the tools (you can install them with pip):
```bash
pip install osmnx networkx matplotlib shapely geopandas contextily numpy tqdm pandas pypinyin matplotlib-scalebar
```

### Input Data Format

Prepare a file named `metrostation.CSV` with the following format for each line:
```csv
Station Name (Longitude, Latitude)
```
For example:
```csv
ZhongShan Road (120.3164438, 36.0720179)
```

## 🚀 Getting Started

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/Urbanism-Analysis-Tool.git
    cd Urbanism-Analysis-Tool
    ```

2. Create a virtual environment (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    venv\Scripts\activate     # Windows
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Place your `metrostation.CSV` file in the same directory as the program.

5. Run the Walking Isochrone Generation Tool:
    ```bash
    python walk_isochrone.py
    ```

## 🔍 How It Works

### Walking Isochrone Generation Tool

This tool generates walking isochrones through the following steps:
- 📥 Data Preparation: Retrieve road network data within a 4km radius of the starting point.
- 🌐 Network Analysis: Project coordinates and build a network model.
- ⏱️ Isochrone Calculation: Generate a 1000-meter walking isochrone.
- 🎨 Visualization Output: Generate a beautiful map and save it as a PNG file.

The generated map files will be saved in the `Isochrone Results` folder, with filenames in the following format:
```plaintext
StationName_1000m_Walking_Isochrone.png
```

## 🌟 Features

- 🔄 Batch processing of multiple starting points
- 🧩 Automatically process and simplify isochrone outlines
- 🗺️ Integrate OpenStreetMap base maps
- 📏 Automatically add scale bars and legends
- 🌈 Beautiful visualization effects

## 🛠️ Tips

- If you encounter errors reading the coordinate file, please check if the file format is correct.
- The program will automatically convert Chinese station names to pinyin for file naming.
- The default generated isochrones are blue lines, and the starting point is marked with a red star.

## 📞 Feedback and Contributions

Feel free to raise issues and suggestions! You can contribute your code and ideas by creating issues or pull requests.

---

Give it a try! If you have any questions or suggestions, feel free to provide feedback~ 😊


---

Thank you for your attention and support for the Urbanism Analysis Tool project!
