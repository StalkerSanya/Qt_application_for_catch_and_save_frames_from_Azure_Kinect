# Qt application to catch and save frames from Azure Kinect

## Introduction

Qt application allows to catch frames from Azure Kinect device and save them on local storage device. 

## Requirements

- OpenCV
- Open3D
- PySide6
- [Driver for Azure Kinect device](https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/develop/docs/usage.md) 

##  Running on Ubuntu 20.04

1. Connect azure kinect device and run:
   ``` python main.py --config azure_kinect_config.json --output <folder_to_save_images>```

2. Click "Start" button" in application window. 
3. To save color and depth image click "Photo" button.
