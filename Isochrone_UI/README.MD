
---

# Isochrone_UI

Isochrone_UI is a tool for urban analysis that supports generating isochrones and outputting results in various formats. This version implements visualization and UI operations. Below are the main features and usage instructions of this tool.

## Main Features

### 1. Complete Isochrone Generation Logic
- **Added generate_isochrone method**: Includes the complete 4-step isochrone generation process:
  1. Download road network data
  2. Construct and project the walking network
  3. Calculate the isochrone range
  4. Generate visual map output

### 2. Feature Enhancements
- **Dynamic walking distance**: Use the distance setting on the interface (adjustable from 500m to 5000m, default is 1000m)
- **Chinese name processing**: Use `pypinyin` to automatically convert Chinese site names to pinyin
- **Multi-format output**: Output both PNG maps and Shapefile vector files simultaneously
- **Progress feedback**: Detailed progress updates are displayed on the interface

### 3. Progress Report Optimization
- **Calculate overall progress percentage based on the number of points**
- **Clear progress feedback for each processing step**
- **Report progress one by one when processing multiple points**

### 4. Error Handling
- **Enhanced exception capture and handling**
- **Single-point errors will not cause the entire batch process to fail**
- **Detailed error information display**

## Usage Instructions

### Select Input File
- Supports input files in CSV, TXT, and Excel formats.

### Set Output Directory
- Select the output directory for generated results.

### Adjust Walking Distance
- The default walking distance is 1000 meters, adjustable between 500 meters and 5000 meters.

### Start Processing
- Click the "Generate Isochrones" button to start processing and view the progress feedback.

### View Results
- After processing is completed, view the results in the output directory. The program generates two result files for each coordinate point:
  - **PNG format map**: Includes base map, road network, and isochrone contours.
  - **Shapefile format vector file**: Can be further edited in GIS software.

# Caution! The map point selection feature currently cannot automatically input coordinates. This will be fixed in future versions.

## Interaction and UI Improvements

### Cancel Selection Methods
- **Cancel button**: Displayed when the selection mode is activated.
- **ESC key**: Press the ESC key to cancel the selection mode.
- **Right-click on the map**: Right-click on the map to cancel the selection mode.
- **Status prompt update**: Inform the user that they can use ESC or right-click to cancel the selection mode.

### Confirm Button
- **New confirm button**: Added a green "Confirm Point" button to the status bar below the map.
- **Improved selection process**:
  - Enable the confirm button and save the temporarily selected coordinates after clicking on the map.
  - The edit dialog will only open after clicking the confirm button.

### Temporary Marker and Status Bar Information
- **Draggable temporary marker**: Click on the map to add a draggable blue marker.
- **Coordinate information pop-up window**: Displays the currently selected coordinates and tips for adjusting the position.
- **Status bar information update**: Displays the precise coordinates of the current selection, and informs the user that they can click the "Confirm Point" button or press the Enter key to confirm.

## Usage Process

1. Click the "Add Point From Map" button to enter selection mode.
2. Read the pop-up operation instructions.
3. Click on the map to add a temporary marker (blue, draggable).
4. Drag the marker to adjust the position if needed.
5. After determining the position, confirm through one of the following methods:
   - Click the "Confirm Point" button at the bottom of the interface
   - Press the Enter key on the keyboard
6. After confirming, the naming dialog will pop up.

This new design retains the simplicity of the operation, improves accuracy and usability, making it easier for you to select and confirm coordinate points.

---
