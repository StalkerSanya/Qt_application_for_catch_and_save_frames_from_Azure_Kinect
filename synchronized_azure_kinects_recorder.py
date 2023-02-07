import os
import sys
import time

import cv2
import argparse
import numpy as np
from PIL import Image
from collections import deque
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
        self.sensor = None
        self.color_frame = None
        self.depth_queue = deque(maxlen=30)
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
                os.mkdir(self.output_dir + "/depth/")
                os.mkdir(self.output_dir + "/depth/raw")
                os.mkdir(self.output_dir + "/depth/mean_30")
            except (PermissionError, FileExistsError):
                print("Unable to mkdir: " + self.output_dir)

    def run(self):
        if self.depth_queue:
            self.depth_queue.clear()
        while self.status:
            try:
                color_frame = Image.open(self.input + "/" + "color.jpg")
                color_frame = np.asarray(color_frame)
                depth_frame = Image.open(self.input + "/" + "depth.png")
                depth_frame = np.asarray(depth_frame, dtype=np.uint16)
            except:
                continue
            self.color_frame = color_frame
            self.depth_queue.append(depth_frame)
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
        time.sleep(1)
        depth_batch = np.asarray(self.depth_queue)
        depth_raw = depth_batch[-1]
        depth_mean = (depth_batch.sum(axis=0)/depth_batch.shape[0]).astype(np.uint16)
        cv2.imwrite(self.output_dir + "/color/" + str(self.number_last_frame) + ".jpg", self.color_frame)
        cv2.imwrite(self.output_dir + "/depth/raw/" + str(self.number_last_frame) + ".png", depth_raw)
        cv2.imwrite(self.output_dir + "/depth/mean_30/" + str(self.number_last_frame) + ".png", depth_mean)
        self.number_last_frame += 1


class Window(QMainWindow):
    def __init__(self, input_master, input_sub, output_master, output_sub):
        super().__init__()
        # Title and dimensions
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
        self.label_master = QLabel(self)
        self.label_master.setFixedSize(640, 480)

        # Create a label for the display camera
        self.label_sub = QLabel(self)
        self.label_sub.setFixedSize(640, 480)

        # Thread in charge of updating the image
        self.camera_master = CameraRGBD(self)
        self.camera_master.set_input(input_master)
        self.camera_master.set_output_dir(output_master)
        self.camera_master.finished.connect(self.close)
        self.camera_master.updateFrame.connect(self.set_image_master)

        # Thread in charge of updating the image
        self.camera_sub = CameraRGBD(self)
        self.camera_sub.set_input(input_sub)
        self.camera_sub.set_output_dir(output_sub)
        self.camera_sub.finished.connect(self.close)
        self.camera_sub.updateFrame.connect(self.set_image_sub)

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
        cameras_layout = QHBoxLayout()
        cameras_layout.addWidget(self.label_master)
        cameras_layout.addWidget(self.label_sub)
        vertical_align_layout = QVBoxLayout()
        vertical_align_layout.addLayout(cameras_layout)
        vertical_align_layout.addLayout(horizontal_buttons_layout)

        # Central widget
        widget = QWidget(self)

        # Connections
        self.button_start.clicked.connect(self.start_master)
        self.button_start.clicked.connect(self.start_sub)
        self.button_stop.clicked.connect(self.kill_thread_master)
        self.button_stop.clicked.connect(self.kill_thread_sub)
        self.button_stop.setEnabled(False)
        self.button_photo.clicked.connect(self.save_frames_master)
        self.button_photo.clicked.connect(self.save_frames_sub)
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
    def kill_thread_master(self):
        print("Finishing...")
        self.button_stop.setEnabled(False)
        self.button_photo.setEnabled(False)
        self.button_start.setEnabled(True)
        self.camera_master.status = False
        # Give time for the camera to finish
        time.sleep(1)
        self.camera_master.terminate()
        # Give time for the thread to finish
        time.sleep(2)
    
    @Slot()
    def kill_thread_sub(self):
        print("Finishing...")
        self.button_stop.setEnabled(False)
        self.button_photo.setEnabled(False)
        self.button_start.setEnabled(True)
        self.camera_sub.status = False
        # Give time for the camera to finish
        time.sleep(1)
        self.camera_sub.terminate()
        # Give time for the thread to finish
        time.sleep(2)

    @Slot()
    def start_master(self):
        print("Starting...")
        self.button_stop.setEnabled(True)
        self.button_photo.setEnabled(True)
        self.button_start.setEnabled(False)
        self.camera_master.start()
    
    @Slot()
    def start_sub(self):
        print("Starting...")
        self.button_stop.setEnabled(True)
        self.button_photo.setEnabled(True)
        self.button_start.setEnabled(False)
        self.camera_sub.start()
    
    @Slot()
    def save_frames_master(self):
        print("Saving frames...")
        self.button_photo.setEnabled(False)
        self.camera_master.save_frames()
        self.button_photo.setEnabled(True)
        print("Saved")
    
    @Slot()
    def save_frames_sub(self):
        print("Saving frames...")
        self.button_photo.setEnabled(False)
        self.camera_sub.save_frames()
        self.button_photo.setEnabled(True)
        print("Saved")

    @Slot(QImage)
    def set_image_master(self, image):
        self.label_master.setPixmap(QPixmap.fromImage(image))
    
    @Slot(QImage)
    def set_image_sub(self, image):
        self.label_sub.setPixmap(QPixmap.fromImage(image))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Azure kinect recorder.')
    parser.add_argument('--input_master', type=str, default="camera_stream_master", help='master input path to catch color and depth images,  Default: camera_stream_master')
    parser.add_argument('--input_sub', type=str, default="camera_stream_sub", help='subordinate input path to catch color and depth images,  Default: camera_stream_sub')
    parser.add_argument('--output_master', type=str, default="frames_master", help='master output path to store color/ and depth/ images,  Default: frames_master')
    parser.add_argument('--output_sub', type=str, default="frames_sub", help='subordinate output path to store color/ and depth/ images,  Default: frames_sub')
    args = parser.parse_args()

    app = QApplication()
    w = Window(args.input_master, args.input_sub, args.output_master, args.output_sub)
    w.show()
    sys.exit(app.exec())