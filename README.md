# Speed & object detection camera

A speed detection system with web interface for speed and car monitoring with analytics. Built upon the core speed detection functionality of [pageauc/speed-camera](https://github.com/pageauc/speed-camera/tree/master). 


## About

- As of now the system only works with RTSP stream.
- [YOLO](https://github.com/ultralytics/ultralytics) object detection integrated with speed camera
- Web UI with detections & speed overview
- Analytics page


![1750208315096](image/README/1750208315096.png)

![1750209348960](image/README/1750209348960.png)

![1750208352554](image/README/1750208352554.png)

![1750209178216](image/README/1750209178216.png)

![1750209198660](image/README/1750209198660.png)

## Yolo models for object 

## Detection

On the settings page yolo v8 models can be automatically downloaded when selected. I havent changed the models they are just default, a better solution would be to customize these models to better adjust them to the use case. Or use the latest versions of yolo. Suggestions would be greatly apprieciated!


## Installation

I recommend deploying this on your home server with docker the web interface is mobile compatible so data can be viewed from there too. (port 5000). Although I havent tested it this could be run on any linux or windows machine as long as there are enough resources for the rtsp stream and detection. 

### Local Installation

1. **Clone Repository**

```bash
git clone https://github.com/your-username/deep-license-plate-recognition.git
cd deep-license-plate-recognition
```

2. **Install Dependencies**

```bash
pip install -r requirements.txt
```

3. **Download YOLO Models**

```bash
# Models will auto-download on first run, or manually:
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8x.pt -P models/
```

4. **Configure Camera**
   Edit `config.json`:

```json
{
  "camera_settings": {
    "rtsp_urls": ["rtsp://username:password@camera_ip:554/stream"]
  }
}
```

5. **Run System**

```bash
# Web interface (recommended)
python speed_camera_web.py

# CLI only
python speed_camera.py
```

Access web interface at `http://localhost:5000`

### Docker Installation

1. **Build Image**

```bash
docker-compose build
```

2. **Configure Environment**

```bash
# Edit docker-compose.yml for your camera settings
# Mount persistent storage for detections/
```

3. **Deploy**

```bash
# GPU-enabled deployment
docker-compose up -d

# CPU-only deployment
docker-compose -f docker-compose.yml -f docker-compose.cpu.yml up -d
```

## Settings

### Camera Calibration

1. Access Settings → Calibration Settings
2. Measure a known object (vehicle length: ~4127mm)
3. Count pixels for same object in camera view
4. Set calibration values for L2R and R2L directions

### Detection Zones

Configure detection areas and speed lines:

- **Detection Area**: Rectangle where motion is detected
- **L2R Line**: Left-to-right speed measurement line
- **R2L Line**: Right-to-left speed measurement line

### Speed Settings

- **Speed Limit**: When detection is marked as a speed violation
- **Min/Max Speed**: Filter unrealistic readings
- **Track Counter**: Minimum detections before speed calculation

## Usage

### Web Interface

- **Dashboard**: Real-time monitoring and system status
- **Detections**: View captured violations with images
- **Analytics**: Speed trends and traffic analysis
- **Settings**: System configuration and calibration

### Data Export

- **CSV Export**: Detection logs with timestamps and metadata
- **Image Archive**: Annotated violation images
- **Analytics Export**: Traffic pattern reports

## API Endpoints

- `GET /api/status` - System status
- `GET /api/detections` - Detection history
- `GET /api/analytics` - Traffic analytics
- `POST /api/config` - Update configuration
- `GET /api/stream` - Live video feed

## Troubleshooting

### GPU Issues

```bash
# Check if PyTorch can detect GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Check GPU status (if NVIDIA GPU present)
nvidia-smi
```

**Note**: GPU acceleration is automatic - no CUDA Toolkit installation required. PyTorch handles GPU detection and falls back to CPU if needed.

### Camera Connection

- Verify RTSP URL with VLC or similar player
- Check network connectivity to camera
- Ensure credentials are correct

### Performance Optimization

- Use GPU acceleration when available
- Adjust detection area to reduce processing load
- Lower RTSP resolution if needed
- Increase `min_area` to filter small objects

## Development

### Project Structure

```
├── speed_camera.py          # Core detection engine
├── speed_camera_web.py      # Web interface server
├── config_manager.py        # Configuration management
├── frontend/                # Web UI components
├── models/                  # YOLO model files
├── detections/              # Output images and CSV
└── docker-compose.yml       # Container deployment
```

### Contributing

1. Fork repository
2. Create feature branch
3. Implement changes with tests
4. Submit pull request

## Acknowledgments

This project builds upon the excellent foundation provided by [pageauc/speed-camera](https://github.com/pageauc/speed-camera/tree/master). Key enhancements include:

- Modern web interface with responsive design
- GPU acceleration with YOLO integration
- Advanced analytics and data visualization
- Docker containerization
- Mobile compatibility
- Real-time streaming dashboard

## License

MIT License - see LICENSE file for details.

## Legal Disclaimer

**⚠️ IMPORTANT LEGAL NOTICE ⚠️**

This software is provided for **educational and research purposes only**. The publisher/maintainer(s) of this repository:

- **Assume NO responsibility** for how this software is used
- **Provide NO legal advice** regarding traffic monitoring laws
- **Make NO warranties** about compliance with local regulations
- **Accept NO liability** for any legal consequences of use

### User Responsibilities

**YOU are solely responsible for:**

- ✅ Ensuring compliance with local, state, and federal laws
- ✅ Obtaining necessary permits or authorizations
- ✅ Respecting privacy rights and data protection laws
- ✅ Using this software only where legally permitted
- ✅ Consulting with legal counsel before deployment

### Prohibited Uses

This software **MUST NOT** be used for:

- ❌ Unauthorized traffic enforcement on public roads
- ❌ Violating privacy laws or regulations
- ❌ Commercial speed enforcement without proper licensing
- ❌ Any illegal surveillance activities

### No Endorsement

Publication of this code does **NOT constitute**:

- Legal advice or guidance
- Endorsement of any particular use case
- Warranty of legal compliance
- Authorization to use in any jurisdiction

**USE AT YOUR OWN RISK AND LEGAL RESPONSIBILITY**

---

**By downloading, using, or deploying this software, you acknowledge that you have read this disclaimer and agree to assume all legal responsibility for your use of this system.**

## Support

- **Issues**: GitHub Issues tracker
- **Documentation**: Wiki pages
- **Discussions**: GitHub Discussions

---

**Note**: Ensure compliance with local traffic monitoring regulations and privacy laws when deploying this system.
