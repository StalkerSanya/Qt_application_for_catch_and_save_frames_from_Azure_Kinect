import os
import sys
import time
from datetime import datetime
import cv2
import open3d as o3d
import argparse
import numpy as np
from collections import deque
from PySide6.QtCore import Qt, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (QApplication, QComboBox, QGroupBox,
                               QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget, QSlider)



"""This example uses the video from a  webcam to apply pattern
detection from the OpenCV module. e.g.: face, eyes, body, etc."""


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

    def set_sensor(self, sensor):
        self.sensor = sensor
    
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
            rgbd = self.sensor.capture_frame(self.align_depth_to_color)
            if rgbd is None:
                continue
            self.color_frame = cv2.cvtColor(np.asarray(rgbd.color), cv2.COLOR_BGR2RGB)
            depth_frame = np.asarray(rgbd.depth)
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
        current_datetime = datetime.now()
        unique_image_name = str(current_datetime.year) + "-" \
                            + str(current_datetime.month) + "-" \
                            + str(current_datetime.day) + "_" \
                            + str(current_datetime.hour) + "-" \
                            + str(current_datetime.minute) + "-" \
                            + str(current_datetime.second)
        cv2.imwrite(self.output_dir + "/color/" + unique_image_name + ".jpg", self.color_frame)
        depth_batch = np.asarray(self.depth_queue)
        depth_raw = depth_batch[-1]
        depth_mean = (depth_batch.sum(axis=0)/depth_batch.shape[0]).astype(np.uint16)
        cv2.imwrite(self.output_dir + "/depth/raw/" + unique_image_name + ".png", depth_raw)
        cv2.imwrite(self.output_dir + "/depth/mean_30/" + unique_image_name + ".png", depth_mean)
        print("frame ", self.number_last_frame)
        self.number_last_frame += 1



class Window(QMainWindow):
    def __init__(self, sensor, output_dir):
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
        self.label = QLabel(self)
        self.label.setFixedSize(640, 480)

        # Thread in charge of updating the image
        self.th = CameraRGBD(self)
        self.th.set_sensor(sensor)
        self.th.set_output_dir(output_dir)
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

        # Sound Effect for ending of saving frames event 
        self.effect = QSoundEffect()
        self.effect.setSource(QUrl.fromLocalFile("zatvor.wav"))
        self.effect.setVolume(1.00)

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

    def keyPressEvent(self, event):
        if event.key() == 16777239: # clicker button code
            print("Saving frames...")
            self.button_photo.setEnabled(False)
            self.th.save_frames()
            self.button_photo.setEnabled(True)
            self.effect.play()
            print("Saved")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Azure kinect recorder.')
    parser.add_argument('--config', type=str, help='input json kinect config')
    parser.add_argument('--list', action='store_true', help='list available azure kinect sensors')
    parser.add_argument('--device', type=int, default=0, help='input kinect device id')
    parser.add_argument('--output', type=str, default="frames", help='output path to store color/ and depth/ images,  Default: frames')
    args = parser.parse_args()

    if args.list:
        o3d.io.AzureKinectSensor.list_devices()
        exit()

    if args.config is not None:
        config = o3d.io.read_azure_kinect_sensor_config(args.config)
    else:
        config = o3d.io.AzureKinectSensorConfig()
    sensor = o3d.io.AzureKinectSensor(config)

    device = args.device
    if device < 0 or device > 255:
        print('Unsupported device id, fall back to 0')
        device = 0

    if not sensor.connect(device):
        raise RuntimeError('Failed to connect to sensor')
    
    app = QApplication()
    w = Window(sensor, args.output)
    w.show()
    sys.exit(app.exec())