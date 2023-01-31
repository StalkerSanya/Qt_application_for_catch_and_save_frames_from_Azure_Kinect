import os
import sys
import time

import cv2
import argparse
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget, QSlider)


class CameraRGBD(QThread):
    updateFrame = Signal(QImage)

    def __init__(self, parent=None):
        QThread.__init__(self, parent)
        self.status = True
        self.input = None
        self.color_frame = None
        self.depth_frame = None
        self.output_dir = None
        self.number_last_frame = 1
        self.align_depth_to_color = True

    def set_input(self, input):
        self.input = input
    
    def set_output_dir(self, output_dir):
        self.output_dir = output_dir
        if self.output_dir is None:
            self.output_dir = "frames"

        if (os.path.isdir(self.output_dir + "/color") and os.path.isdir(self.output_dir + "/depth")):
            print('Output directory \'{}\' already existing, continue recording there'.format(self.output_dir))
            for path in os.listdir(self.output_dir + "/color"):
                # check if current path is a file
                if os.path.isfile(os.path.join(self.output_dir + "/color", path)):
                    self.number_last_frame += 1
        else:
            try:
                os.mkdir(self.output_dir)
                os.mkdir(self.output_dir + "/color")
                os.mkdir(self.output_dir + "/depth")
            except (PermissionError, FileExistsError):
                print("Unable to mkdir: " + self.output_dir)
    

    def run(self):
        while self.status:
            try:
                color_frame = Image.open(self.input + "/" + "color.jpg")
                color_frame = np.asarray(color_frame)
                depth_frame = Image.open(self.input + "/" + "depth.png")
                depth_frame = np.asarray(depth_frame, dtype=np.uint16)
            except:
                continue
            self.color_frame = color_frame
            self.depth_frame = depth_frame
            # Creating and scaling QImage
            h, w, ch = self.color_frame.shape
            img = QImage(self.color_frame.data, w, h, ch * w, QImage.Format_BGR888)
            scaled_img = img.scaled(640, 480, Qt.KeepAspectRatio)
            # Emit signal
            self.updateFrame.emit(scaled_img)

    @Slot(int)
    def adjust_x(self, value):
        self.set_x(value)
        
    @Slot()
    def save_frames(self):
        cv2.imwrite(self.output_dir + "/color/" + str(self.number_last_frame) + ".jpg", self.color_frame)
        cv2.imwrite(self.output_dir + "/depth/" + str(self.number_last_frame) + ".png", self.depth_frame)
        self.number_last_frame += 1



class Window(QMainWindow):
    def __init__(self, input, output):
        super().__init__()
        # Title and dimensions
        # config = o3d.io.AzureKinectSensorConfig()
        # self.sensor = o3d.io.AzureKinectSensor(config)
        # if not self.sensor.connect(0):
        #     raise RuntimeError('Failed to connect to sensor')
        self.setWindowTitle("Patterns detection")
        self.setGeometry(0, 0, 800, 500)

        # Main menu bar
        self.menu = self.menuBar()
        self.menu_file = self.menu.addMenu("File")
        exit = QAction("Exit", self, triggered=qApp.quit)
        self.menu_file.addAction(exit)

        self.menu_about = self.menu.addMenu("&About")
        about = QAction("About Qt", self, shortcut=QKeySequence(QKeySequence.HelpContents),
                        triggered=qApp.aboutQt)
        self.menu_about.addAction(about)

        # Create a label for the display camera
        self.label = QLabel(self)
        self.label.setFixedSize(640, 480)

        # Thread in charge of updating the image
        self.th = CameraRGBD(self)
        self.th.set_input(input)
        self.th.set_output_dir(output)
        self.th.finished.connect(self.close)
        self.th.updateFrame.connect(self.setImage)

        # Buttons layout
        horizontal_buttons_layout = QHBoxLayout()
        self.button_start = QPushButton("Start")
        self.button_stop = QPushButton("Stop/Close")
        self.button_photo = QPushButton("Photo")
        self.button_start.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.button_stop.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.button_photo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        horizontal_buttons_layout.addWidget(self.button_start)
        horizontal_buttons_layout.addWidget(self.button_stop)

        # Align verticaly label_layout lauout with horizontal_buttons_layout
        vertical_align_layout = QVBoxLayout()
        vertical_align_layout.addWidget(self.label)
        vertical_align_layout.addLayout(horizontal_buttons_layout)

        # Central widget
        widget = QWidget(self)

        # Connections
        self.button_start.clicked.connect(self.start)
        self.button_stop.clicked.connect(self.kill_thread)
        self.button_stop.setEnabled(False)
        self.button_photo.clicked.connect(self.save_frames)
        self.button_photo.setEnabled(False)

        # Layout for button_photo
        vertical_buttons_layout = QVBoxLayout()
        vertical_buttons_layout.setAlignment(Qt.AlignTop)
        vertical_buttons_layout.addWidget(self.button_photo) 
        
        # Main layout to align left layout and right layout
        main_layout = QHBoxLayout()
        main_layout.addLayout(vertical_align_layout)
        main_layout.addLayout(vertical_buttons_layout)

        widget.setLayout(main_layout)
        self.setCentralWidget(widget)

    @Slot()
    def kill_thread(self):
        print("Finishing...")
        self.button_stop.setEnabled(False)
        self.button_photo.setEnabled(False)
        self.button_start.setEnabled(True)
        self.th.status = False
        # Give time for the camera to finish
        time.sleep(1)
        self.th.terminate()
        # Give time for the thread to finish
        time.sleep(2)

    @Slot()
    def start(self):
        print("Starting...")
        self.button_stop.setEnabled(True)
        self.button_photo.setEnabled(True)
        self.button_start.setEnabled(False)
        self.th.start()
    
    @Slot()
    def save_frames(self):
        print("Saving frames...")
        self.button_photo.setEnabled(False)
        self.th.save_frames()
        self.button_photo.setEnabled(True)
        print("Saved")

    @Slot(QImage)
    def setImage(self, image):
        self.label.setPixmap(QPixmap.fromImage(image))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Azure kinect recorder.')
    parser.add_argument('--input', type=str, default="camera_stream", help='input path to catch color and depth images,  Default: camera_stream')
    parser.add_argument('--output', type=str, default="frames", help='output path to store color/ and depth/ images,  Default: frames')
    args = parser.parse_args()

    app = QApplication()
    w = Window(args.input, args.output)
    w.show()
    sys.exit(app.exec())