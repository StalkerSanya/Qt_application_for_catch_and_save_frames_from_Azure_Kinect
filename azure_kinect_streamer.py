import open3d as o3d
import argparse
import cv2
import os
import numpy as np

class AzureKinectStreamer:
    
    def __init__(self, device = 0, config_json = None, output = "camera_stream"):
        if device < 0 or device > 255:
            print('Unsupported device id, fall back to 0')
            device = 0
        self.device = device
        if config_json is not None:
            config = o3d.io.read_azure_kinect_sensor_config(config_json)
        else:
            config = o3d.io.AzureKinectSensorConfig()
        self.sensor = o3d.io.AzureKinectSensor(config)
        if not self.sensor.connect(device):
            raise RuntimeError('Failed to connect to sensor')
        self.output = output
        if self.output is None:
            self.output = "camera_stream"
        if (os.path.isdir(self.output)):
            print('Output stream-directory \'{}\' already existing, continue streaming there'.format(self.output))
        else:
            try:
                os.mkdir(self.output)
            except (PermissionError, FileExistsError):
                print("Unable to mkdir: " + self.output)
    
    def run(self):
         while True: 
            rgbd = self.sensor.capture_frame(True)
            if rgbd is None:
                continue
            color_frame = np.asarray(rgbd.color)
            depth_frame = np.asarray(rgbd.depth)
            key = cv2.waitKey(30)
            if key == 27: # pushed Esc
                break
            else:
                cv2.imwrite(self.output + "/" + "color.jpg", color_frame)
                cv2.imwrite(self.output + "/" + "depth.png", depth_frame)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Azure kinect recorder.')
    parser.add_argument('--config', type=str, help='input json kinect config')
    parser.add_argument('--list', action='store_true', help='list available azure kinect sensors')
    parser.add_argument('--device', type=int, default=0, help='input kinect device id')
    parser.add_argument('--output', type=str, default="camera_stream", help='output path to stream color and depth images,  Default: camera_stream')
    args = parser.parse_args()

    if args.list:
        o3d.io.AzureKinectSensor.list_devices()
        exit()

    azure_kinect_streamer = AzureKinectStreamer(device=args.device, config_json=args.config, output=args.output)
    azure_kinect_streamer.run()
    
    