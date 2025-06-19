# Speed & object detection camera

A speed detection system with a real time web interface for speed and car monitoring with analytics. Built upon the core speed detection functionality of [pageauc/speed-camera](https://github.com/pageauc/speed-camera/tree/master).

## Introduction
This system can detect and measure the speed of objects. It works by monitoring the rtsp stream and waiting for motion the speed is being measured but only logs when the object detection algorithm detects this too (can be changed in settings), an image is saved with the speed of the object, color, object type (eg, car, person, anything). This can be viewed on the detections page and on the analytics page which gives and comprehensive overview.

- Dashboard
- Settings
- Detections
- Analytics


## Yolo models for object Detection

On the settings page yolo v8 models can be automatically downloaded when selected. I havent changed the models they are just default, a better solution would be to customize these models to better adjust them to the use case. Or use the latest versions of yolo. Suggestions would be greatly appreciated! [YOLO](https://github.com/ultralytics/ultralytics)

## Installation
I recommend deploying this on your home server with docker the web interface is mobile compatible so data can be viewed from there too. Although I havent tested it this could be run on a raspberry pi, as long as there are enough resources for the rtsp stream and detection. So far this works on my home docker server with tailscale for acces outside the home network.

The webserver can be accesed at <http:localhost:5000> Note HTTP not HTTPS.

### Prerequisites

- **Python 3.9+** (for local installation)
- **Docker & Docker Compose** (for Docker installation)
- **IP Camera** or camera with RTSP stream capability

### Method 1: Docker Installation (Recommended)

1. **Download the Application**

   ```bash
   git clone https://github.com/[your-username]/speed-object-detection-camera.git
   cd speed-object-detection-camera
   ```
2. **Configure Your Camera**

   Edit `config.json` with your RTSP camera details before building.
3. **Build and Run with Docker**

   ```bash
   docker-compose up -d
   ```
4. **Access the Web Interface**

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

   Edit `config.json` with your camera details:

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

- **YOLO Models**: The YOLOv8 nano model is included but its highly recommended to download a better model models are saved in the models/ folder
- **Detection Data**: All speed detections and images are saved in the `detections/` folder
- **GPU Support**: Automatically uses GPU if available, falls back to CPU, (can be toggled in settings)
- **Mobile Friendly**: The web interface works on mobile devices

## Settings
For an more in-dept guide on how to calibrate the camera I recommended [pageauc/speed-camera/wiki](https://github.com/pageauc/speed-camera/wiki/Calibrate-Camera-for-Distance).
![image](https://github.com/user-attachments/assets/248a1d8f-54bb-471b-9a10-d2dc118ad066)

![image](https://github.com/user-attachments/assets/17fd439c-e190-4f23-85c0-5925ff626747)

Most settings can be updated and change live like the detection lines, some settings however require a camera restart (stop/start).

### Camera Settings
- **RTSP URL**: Common RTSP [protocols](https://www.getscw.com/decoding/rtsp)
- **Camera Framerate**

### Detection Settings
- **YOLO Models**: See [Yolo models for object Detection](#yolo-models-for-object-detection)
- **Confidence treshold**: This can be adjusted to adjust the confidence of the yolo model when it classifies something as that object
- **Use GPU**: defaults to cpu if no GPU can be found.
- **Min Detection Area**: Can be adjusted to filter small detections
- **Motion Sensitivity**: Removes noise from the detection Smaller values (1-5) are more sensitive to small movements but may detect noise, while larger values (10-50) reduce false detections from shadows and small movements but may miss smaller vehicles. Default is 10
 

### Speed Detection Settings
- **Speed limit**: If an object exceeds this limit its flagged as an violation on the detections page
- **Speed in mph**
- **Minimum Speed/maximum Speed**: Filters unrealistically slow or fast speeds
- **Min/max time difference**: The time a vehicle must be tracked before the system will calculate its speed.
- **Min track length**: Minimum distance in pixels vehicle must travel
- Track Counter
  - Number of frames a car must travel
  - 
Higher values = more accurate speed (more data points), but slower detection
Lower values = faster detection, but potentially less accurate


1. Access Settings → Calibration Settings
2. Measure a known object like the vehicle length [lookup vehicle dimensions]https://www.automobiledimension.com
3. Count pixels for same object in camera view
4. Set calibration values.

### Detection Zones

Configure detection area and speed lines:

- **Left to right enabled** & **Right to Left enabled**:Allow detection only in one direction
- **L2R Line**: Left-to-right speed measurement line position
- **R2L Line**: Right-to-left speed measurement line position
- **Detection Area Top, Bottom, left and right**: the detection area margins

### Calibration Settings

### Output Settings
- **Save Images** When disabled the detections still get recorded but no image is saved a placeholder is used instead of an image.
- **Image Quality** JPEG image quality reduce file size


## Troubleshooting

### Cant connect to the webpage
- Make sure to use http and not https
- Check if port is not already in use defaults to 5000

### Camera Connection

- Verify RTSP URL with VLC or similar player

### Performance Optimization

- Use GPU if possible
- Smaller YOLO model



## License
   Apache-2.0 license
   Copyright [2025] [julbov]
**Note**:This software is provided for educational and research purposes only. The author is not responsible for any misuse or violation of local laws. It is your responsibility to ensure legal compliance in your jurisdiction.
