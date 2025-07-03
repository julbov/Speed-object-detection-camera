# Speed & Object Detection Camera

A speed monitoring and object detection system with a real-time web interface.

## Introduction
This system detects and measures the speed of moving objects by watching the RTSP video stream for motion. Speed is only recorded when an object is also recognized by the detection algorithm (this can be changed in the settings). Each detection saves an image along with the object's speed, color, and type (e.g., car, person, etc.). These results are shown on the detections page and summarized on the analytics page for a clear overview.


| | | 
|:-------------------------:|:-------------------------:|
<img width="" height="" alt="dashboard" src="https://github.com/user-attachments/assets/415fe6a4-0b96-405c-ae19-decc4a130ed8">  Dashboard |  <img width="" height="" alt="detections" src="https://github.com/user-attachments/assets/c85a35b5-3884-4a65-8b92-245bc6b1e56c"> Detections |
<img height="" alt="analytics" src="https://github.com/user-attachments/assets/8c7edc98-ec7b-4f9f-bd52-96738a620ef9"> Analytics | <img height="" alt="analytics" src="https://github.com/user-attachments/assets/4eb853cd-51f7-4c47-975c-05f496375cb4"><br>Analytics |

## Yolo Models for Object Detection
On the settings page, YOLOv8 models can be automatically downloaded when selected. A better solution would be to customize these models to better adjust them to your use case. Or use the latest versions of YOLO. Suggestions would be greatly appreciated!  
[Link to the YOLO models](https://github.com/ultralytics/ultralytics)

## Installation
I recommend running this on a home server using Docker. The web interface works well on mobile devices, so you can check detections from anywhere. While not tested, it may also run on a Raspberry Pi if it has enough resources for the RTSP stream and detection. It currently runs on my home Docker server with Tailscale for remote access.

The web server can be accessed at <http://localhost:5000> (HTTP not HTTPS)

### Prerequisites

- **Python 3.9+** (for local installation)
- **Docker & Docker Compose** (for Docker installation)
- **IP Camera** or camera with RTSP stream capability

### Method 1: Docker Installation (Recommended)

1. **Download the Application**

   ```bash
   git clone https://github.com/julbov/speed-object-detection-camera.git
   cd speed-object-detection-camera
   ```

2. **Build and Run with Docker**

   ```bash
   docker-compose up -d
   ```

3. **Access the Web Interface**

   Go to: `http://localhost:5000`

### Method 2: Local Installation (Python)

1. **Download the Application**

   ```bash
   git clone https://github.com/julbov/speed-object-detection-camera.git
   cd speed-object-detection-camera
   ```

2. **Install Python Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Your Camera**

   Edit `config.json` with your RTSP URL details:

   ```json
   {
     "camera_settings": {
       "rtsp_url": "rtsp://username:password@your-camera-ip:554/h264"
     }
   }
   ```

4. **Run the Application**

   ```bash
   python speed_camera_web.py
   ```

5. **Access the Web Interface**

   Go to: `http://localhost:5000`

### Quick Start Notes

- **YOLO Models**: The YOLOv8 nano model is included, but it’s highly recommended to download a better model. Models are saved in the `models/` folder.
- **Detection Data**: All speed detections and images are saved in the `detections/` folder.
- **GPU Support**: Can use GPU if available, falls back to CPU (can be toggled in settings).
- **Mobile Friendly**: The web interface works on mobile devices.

## Settings 
![image](https://github.com/user-attachments/assets/248a1d8f-54bb-471b-9a10-d2dc118ad066)

Most settings can be updated and changed live like the detection lines. Some settings, however, require a camera restart (stop/start).

### Camera Settings
- **RTSP URL**: Common RTSP [protocols](https://www.getscw.com/decoding/rtsp)
- **Camera Framerate**

### Detection Settings
- **YOLO Models**: See [Yolo models for object Detection](#yolo-models-for-object-detection)
- **Confidence Threshold**: This can be adjusted to change the confidence of the YOLO model when it classifies something as that object.
- **Use GPU**: Defaults to CPU if no GPU can be found.
- **Min Detection Area**: Can be adjusted to filter small detections.
- **Motion Sensitivity**: Removes noise from detection. Smaller values (1–5) are more sensitive to small movements but may detect noise, while larger values (10–50) reduce false detections from shadows and small movements but may miss smaller vehicles. Default is 10.

### Speed Detection Settings
- **Speed Limit**: If an object exceeds this limit, it's flagged as a violation on the detections page.
- **Speed in MPH**
- **Minimum Speed / Maximum Speed**: Filters unrealistically slow or fast speeds.
- **Min / Max Time Difference**: The time a vehicle must be tracked before the system will calculate its speed.
- **Min Track Length**: Minimum distance in pixels an object must travel.
- **Track Counter**: Number of frames an object must travel.

Higher values = more accurate speed (more data points), but slower detection.  
Lower values = faster detection, but potentially less accurate.

### Detection Zones

Configure detection area and speed lines:

- **Left to Right Enabled** & **Right to Left Enabled**: Allow detection only in one direction.
- **L2R Line**: Left-to-right speed measurement line position.
- **R2L Line**: Right-to-left speed measurement line position.
- **Detection Area Top, Bottom, Left and Right**: The detection area margins.

### Calibration Settings
- **L2R / R2L Object Size in mm**: Real-life size.
- **L2R / R2L Object Size in Pixels**: Size on screen.

**How to Calibrate**
1. Measure a known object like the vehicle length. [Lookup vehicle dimensions](https://www.automobiledimension.com)
2. Count pixels for the same object in the camera view.
3. Set calibration values.  
For a more in-depth guide on how to calibrate the camera, I recommend [this guide](https://github.com/pageauc/speed-camera/wiki/Calibrate-Camera-for-Distance) from @pageauc.

### Output Settings
- **Save Images**: When disabled, the detections still get recorded but no image is saved. A placeholder is used instead of an image.
- **Image Quality**: JPEG image quality to reduce file size.

### Vehicle Settings
- **Ignore YOLO Validation**: If enabled, every object that gets detected by YOLO gets logged. If it can't be classified, it gets the class "unknown".
- **Vehicle Classes**: Specify classes that are considered valid. These classes are also shown in the analytics and detection page.

## Troubleshooting

### Can't Connect to the Webpage
- Make sure to use HTTP and not HTTPS.
- Check if port 5000 is already in use.

### Camera Connection
- Verify RTSP URL with VLC or a similar player.

Thanks to [pageauc/speed-camera](https://github.com/pageauc/speed-camera/tree/master) for the speed functionality.

## License
Apache-2.0 license  
Copyright [2025] [julbov]  
**Note**: This software is provided for educational and research purposes only. The author is not responsible for any misuse or violation of local laws. It is your responsibility to ensure legal compliance in your jurisdiction.
