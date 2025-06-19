#!/usr/bin/env python3
"""
Speed Detection Camera
Educational and Research Use Only

LEGAL DISCLAIMER:
This software is provided for educational and research purposes only.
Users are solely responsible for ensuring compliance with all applicable
laws and regulations. The authors assume no liability for any use of this
software. Consult legal counsel before deployment.
"""

import os
import cv2
import numpy as np
import time
import math
import csv
import torch
import threading
import queue
from datetime import datetime
from ultralytics import YOLO
import torch
from concurrent.futures import ThreadPoolExecutor
from config_manager import config_manager

class FrameBuffer:
    def __init__(self, maxsize=30):
        self.queue = queue.Queue(maxsize=maxsize)
        self.lock = threading.Lock()
        self.error_count = 0
        self.total_frames = 0
        
    def put(self, frame, timeout=0.1):
        try:
            self.queue.put(frame, timeout=timeout)
            with self.lock:
                self.total_frames += 1
            return True
        except queue.Full:
            return False
    
    def get(self, timeout=1.0):
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def add_error(self):
        with self.lock:
            self.error_count += 1
    
    def get_stats(self):
        with self.lock:
            return {
                'total_frames': self.total_frames,
                'error_count': self.error_count,
                'queue_size': self.queue.qsize(),
                'error_rate': self.error_count / max(1, self.total_frames) * 100
            }

class VehicleTrack:
    
    def __init__(self, track_id, x, y, w, h, timestamp, config=None):
        self.track_id = track_id
        self.start_x = x + w/2  # Use center coordinates
        self.start_y = y + h/2
        self.current_x = x + w/2
        self.current_y = y + h/2
        self.width = w
        self.height = h
        self.start_time = timestamp
        self.last_update = timestamp
        self.positions = [(x + w/2, y + h/2, timestamp)]  # Store center x, y, timestamp
        self.speed_kmh = 0
        self.speed_mph = 0
        self.speed_calculated = False
        self.crossed_line = False
        self.direction = None
        self.vehicle_type = "vehicle"
        self.vehicle_color = "unknown"
        self.confidence = 0.5
        self.config = config or config_manager
        
        self._debug_logged = False
        self._failure_logged = False
        self._speed_attempt_logged = False

    def update_position(self, x, y, w, h, timestamp):
        center_x = x + w/2
        center_y = y + h/2
        
        self.positions.append((center_x, center_y, timestamp))
        if len(self.positions) > 10:
            self.positions.pop(0)
        
        self.current_x = center_x
        self.current_y = center_y
        self.last_update = timestamp
        self.width = w
        self.height = h
        
        if abs(self.current_x - self.start_x) > 20:
            if self.current_x > self.start_x:
                self.direction = 'L2R'
            else:
                self.direction = 'R2L'
    
    def calculate_speed(self):
        if len(self.positions) < 2 or self.speed_calculated:
            return False
        
        l2r_enabled = self.config.get('detection_zones.l2r_enabled', True)
        r2l_enabled = self.config.get('detection_zones.r2l_enabled', True)
        l2r_line_x = self.config.get('detection_zones.l2r_line_x', 400)
        r2l_line_x = self.config.get('detection_zones.r2l_line_x', 1400)
        
        line_crossed = False
        
        if self.direction == 'L2R' and l2r_enabled:
            for i in range(len(self.positions) - 1):
                x1, _, _ = self.positions[i]
                x2, _, _ = self.positions[i + 1]
                if x1 < l2r_line_x <= x2:
                    line_crossed = True
                    break
        elif self.direction == 'R2L' and r2l_enabled:
            for i in range(len(self.positions) - 1):
                x1, _, _ = self.positions[i]
                x2, _, _ = self.positions[i + 1]
                if x1 > r2l_line_x >= x2:
                    line_crossed = True
                    break
        
        if not line_crossed:
            if not self._failure_logged:
                import logging
                logging.debug(f"❌ Track {self.track_id}: No line crossing - Path: {self.positions[0][0]:.0f}px → {self.positions[-1][0]:.0f}px")
                self._failure_logged = True
            return False
        
        start_pos = self.positions[0]
        end_pos = self.positions[-1]
        
        if len(self.positions) > 4:
            quarter_idx = len(self.positions) // 4
            three_quarter_idx = 3 * len(self.positions) // 4
            start_pos = self.positions[quarter_idx]
            end_pos = self.positions[three_quarter_idx]
        
        distance_px = abs(end_pos[0] - start_pos[0])
        time_diff = end_pos[2] - start_pos[2]
        
        min_time_diff = self.config.get('speed_settings.min_time_diff', 0.3)
        min_track_length = self.config.get('speed_settings.min_track_length', 50)
        
        if not self._debug_logged:
            print(f"🔧 Track {self.track_id}: Testing speed - {distance_px:.0f}px in {time_diff:.1f}s")
            self._debug_logged = True
        
        if time_diff > min_time_diff and distance_px > min_track_length:
            cal_obj_px_l2r = self.config.get('calibration_settings.cal_obj_px_l2r', 261)
            cal_obj_mm_l2r = self.config.get('calibration_settings.cal_obj_mm_l2r', 4127)
            cal_obj_px_r2l = self.config.get('calibration_settings.cal_obj_px_r2l', 261)
            cal_obj_mm_r2l = self.config.get('calibration_settings.cal_obj_mm_r2l', 4127)
            
            pixels_to_mm_ratio_l2r = cal_obj_mm_l2r / cal_obj_px_l2r
            pixels_to_mm_ratio_r2l = cal_obj_mm_r2l / cal_obj_px_r2l
            
            if self.direction == 'L2R':
                distance_mm = distance_px * pixels_to_mm_ratio_l2r
            else:
                distance_mm = distance_px * pixels_to_mm_ratio_r2l
            
            distance_m = distance_mm / 1000.0
            speed_ms = distance_m / time_diff
            self.speed_kmh = speed_ms * 3.6
            self.speed_mph = self.speed_kmh * 0.621371
            
            speed_mph = self.config.get('speed_settings.speed_mph', False)
            min_speed_over = self.config.get('speed_settings.min_speed_over', 5)
            max_speed_over = self.config.get('speed_settings.max_speed_over', 200)
            
            speed_check = self.speed_mph if speed_mph else self.speed_kmh
            
            print(f"🏁 Track {self.track_id}: {self.speed_kmh:.1f} km/h - {'✅ VALID' if min_speed_over <= speed_check <= max_speed_over else '❌ INVALID'}")
            
            if min_speed_over <= speed_check <= max_speed_over:
                self.speed_calculated = True
                self.crossed_line = True
                return True
            else:
                return False
        
        if not self._failure_logged:
            reasons = []
            if time_diff <= min_time_diff:
                reasons.append(f"time<{min_time_diff}s")
            if distance_px <= min_track_length:
                reasons.append(f"dist<{min_track_length}px")
            if reasons:
                print(f"❌ Track {self.track_id}: Failed - {', '.join(reasons)}")
            self._failure_logged = True
        
        return False
    
    def is_valid_for_logging(self):
        min_track_length = self.config.get('speed_settings.min_track_length', 50)
        return (self.speed_calculated and 
                abs(self.current_x - self.start_x) > min_track_length and
                self.crossed_line)

class VehicleColorDetector:
    
    def __init__(self, use_gpu=True):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        
        self.color_ranges = {
            'red': [
                (np.array([0, 50, 50]), np.array([10, 255, 255])),
                (np.array([170, 50, 50]), np.array([180, 255, 255]))
            ],
            'blue': [(np.array([100, 50, 50]), np.array([130, 255, 255]))],
            'green': [(np.array([40, 50, 50]), np.array([80, 255, 255]))],
            'yellow': [(np.array([20, 50, 50]), np.array([30, 255, 255]))],
            'orange': [(np.array([10, 50, 50]), np.array([20, 255, 255]))],
            'white': [(np.array([0, 0, 200]), np.array([180, 30, 255]))],
            'black': [(np.array([0, 0, 0]), np.array([180, 255, 50]))],
            'gray': [(np.array([0, 0, 50]), np.array([180, 30, 200]))],
            'silver': [(np.array([0, 0, 100]), np.array([180, 50, 200]))],
            'brown': [(np.array([10, 50, 20]), np.array([20, 255, 200]))]
        }
        
        if self.use_gpu:
            print("🚀 GPU color detection enabled")
    
    def detect_color(self, image):
        if image is None or image.size == 0:
            return "unknown"
        
        try:
            # Convert to HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Calculate color percentages
            color_percentages = {}
            total_pixels = hsv.shape[0] * hsv.shape[1]
            
            for color_name, ranges in self.color_ranges.items():
                mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
                
                for lower, upper in ranges:
                    color_mask = cv2.inRange(hsv, lower, upper)
                    mask = cv2.bitwise_or(mask, color_mask)
                
                percentage = (np.sum(mask > 0) / total_pixels) * 100
                color_percentages[color_name] = percentage
            
            # Return the color with highest percentage (minimum 15% to be considered)
            dominant_color = max(color_percentages, key=color_percentages.get)
            if color_percentages[dominant_color] > 15:
                return dominant_color
            else:
                return "unknown"
        except Exception as e:
            print(f"⚠️ Color detection error: {e}")
            return "unknown"

class RTSPDecoder:
    
    def __init__(self, rtsp_url, frame_buffer, max_retries=5):
        self.rtsp_url = rtsp_url
        self.frame_buffer = frame_buffer
        self.max_retries = max_retries
        self.running = False
        self.cap = None
        self.decode_thread = None
        self.retry_count = 0
        self.last_connection_attempt = 0
        self.connection_backoff = 1  # Start with 1 second backoff
        
    def connect(self):
        current_time = time.time()
        
        # Check if we should wait before attempting connection
        if current_time - self.last_connection_attempt < self.connection_backoff:
            return False
        
        self.last_connection_attempt = current_time
        
        # Only print connection message every 30 attempts to reduce spam
        if self.retry_count % 30 == 0:
            print(f"🔗 Connecting to {self.rtsp_url}")
        
        # Use FFmpeg backend directly for RTSP streams
        try:
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            # Configure for better H.264 handling
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            camera_fps = config_manager.get('camera_settings.fps', 25)
            self.cap.set(cv2.CAP_PROP_FPS, camera_fps)
            
            if self.cap.isOpened():
                # Test read multiple frames to ensure stable connection
                for _ in range(3):
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        # Only print success message every 30 attempts or on first success
                        if self.retry_count % 30 == 0 or self.retry_count == 0:
                            print(f"✅ RTSP Connected")
                        # Reset backoff on successful connection
                        self.connection_backoff = 1
                        self.retry_count = 0
                        return True
                
                self.cap.release()
                    
        except Exception:
            if self.cap:
                self.cap.release()
        
        # Increase backoff time (max 30 seconds)
        self.connection_backoff = min(self.connection_backoff * 1.5, 30)
        self.retry_count += 1
        
        # Only print failure message every 50 attempts to reduce spam
        if self.retry_count % 50 == 0:
            print(f"⚠️ RTSP connection issues (Attempt {self.retry_count}, retrying...)")
        
        return False
    
    def decode_loop(self):
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.running:
            try:
                if not self.cap or not self.cap.isOpened():
                    if not self.connect():
                        # Sleep for backoff time or minimum 1 second
                        time.sleep(max(self.connection_backoff, 1))
                        continue
                
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    # Reset error counter on successful read
                    consecutive_errors = 0
                    self.retry_count = 0
                    
                    # Add frame to buffer
                    if not self.frame_buffer.put(frame):
                        # Buffer full, skip frame
                        pass
                        
                else:
                    consecutive_errors += 1
                    self.frame_buffer.add_error()
                    
                    if consecutive_errors >= max_consecutive_errors:
                        # Only print reconnection message every 50 attempts
                        if self.retry_count % 50 == 0:
                            error_msg = f"⚠️ RTSP: Stream interrupted, reconnecting..."
                            print(error_msg)
                        self.cap.release()
                        self.cap = None
                        consecutive_errors = 0
                        time.sleep(1)
                    
            except Exception as e:
                consecutive_errors += 1
                self.frame_buffer.add_error()
                
                # Suppress most decode error messages - they're usually temporary
                if consecutive_errors % 100 == 0:
                    error_msg = f"⚠️ RTSP: Decode issues detected"
                    print(error_msg)
                
                if consecutive_errors >= max_consecutive_errors:
                    # Only print reconnection message every 50 attempts
                    if self.retry_count % 50 == 0:
                        reconnect_msg = "🔄 RTSP: Reconnecting due to decode errors..."
                        print(reconnect_msg)
                    if self.cap:
                        self.cap.release()
                    self.cap = None
                    consecutive_errors = 0
                    time.sleep(2)
    
    def start(self):
        self.running = True
        self.decode_thread = threading.Thread(target=self.decode_loop, daemon=True)
        self.decode_thread.start()
        print("🎬 RTSP decoder started")
    
    def stop(self):
        self.running = False
        if self.decode_thread:
            self.decode_thread.join(timeout=5)
        if self.cap:
            self.cap.release()
        print("🛑 RTSP decoder stopped")

class SpeedCamera:
    
    def __init__(self):
        self.config = config_manager
        
        yolo_model_name = self.config.get('detection_settings.yolo_model', 'yolov8x.pt')
        yolo_model_path = os.path.join('models', yolo_model_name)
        
        if not os.path.exists(yolo_model_path):
            print(f"⚠️ YOLO model not found: {yolo_model_path}")
            fallback_path = os.path.join('models', 'yolov8n.pt')
            if os.path.exists(fallback_path):
                print(f"🔄 Using fallback model: {fallback_path}")
                yolo_model_path = fallback_path
            else:
                raise FileNotFoundError(f"No YOLO models found in models/ directory")
        
        print(f"🤖 Loading YOLO model: {yolo_model_path}")
        self.yolo_model = YOLO(yolo_model_path)
        
        self.setup_gpu()
        
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=True)
        self.color_detector = VehicleColorDetector(self.use_gpu)
        
        self.tracks = {}
        self.track_id_counter = 0
        self.frame_count = 0
        
        self.stats = {
            'frames_processed': 0,
            'moving_logged': 0,
            'stationary_ignored': 0,
            'l2r_count': 0,
            'r2l_count': 0
        }
        
        self.running = False
        self.frame_buffer = FrameBuffer(maxsize=30)
        
        rtsp_urls = self.config.get('camera_settings.rtsp_urls', [])
        if not rtsp_urls:
            raise ValueError("No RTSP URLs configured")
        
        rtsp_url = rtsp_urls[0]
        self.rtsp_decoder = RTSPDecoder(rtsp_url, self.frame_buffer)
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.output_dir = 'detections'
        os.makedirs(self.output_dir, exist_ok=True)
        
        csv_filename = 'object_detections.csv'
        self.csv_file = os.path.join(self.output_dir, csv_filename)
        print(f"📄 CSV file path: {self.csv_file}")
        
        csv_headers = ['timestamp', 'object_type', 'object_color', 'direction', 'speed_kmh', 'speed_mph', 'confidence', 'image_file', 'removed']
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                print(f"✅ CSV file created: {self.csv_file}")
        else:
            print(f"✅ CSV file exists, preserving data: {self.csv_file}")
            self.migrate_csv_if_needed()
            try:
                with open(self.csv_file, 'r') as f:
                    reader = csv.reader(f)
                    next(reader)
                    existing_count = sum(1 for row in reader)
                print(f"📊 Found {existing_count} existing detections in CSV")
            except Exception as e:
                print(f"⚠️ Could not count existing records: {e}")
    
    def migrate_csv_if_needed(self):
        """Add 'removed' column to existing CSV if it doesn't exist"""
        try:
            with open(self.csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                # Check if 'removed' column already exists
                if 'removed' in fieldnames:
                    return  # No migration needed
                
                print("🔄 Migrating CSV file to add 'removed' column...")
                rows = list(reader)
            
            # Add 'removed' column with default value False for all existing rows
            new_fieldnames = list(fieldnames) + ['removed']
            for row in rows:
                row['removed'] = 'False'
            
            # Write back to file with new structure
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=new_fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ CSV migration completed - added 'removed' column to {len(rows)} existing records")
            
        except Exception as e:
            print(f"⚠️ CSV migration failed: {e}")
        print("🚗 Speed Camera System Initialized")
        print(f"📹 RTSP: {self.config.get('camera_settings.rtsp_urls', [''])[0]}")
        print(f"🎯 GPU: {'Enabled' if self.use_gpu else 'CPU only'}")
    
    def setup_gpu(self):
        self.use_gpu = self.config.get('detection_settings.use_gpu', True) and torch.cuda.is_available()
        
        if self.use_gpu and torch.cuda.is_available():
            print(f"🚀 GPU detected: {torch.cuda.get_device_name(0)}")
            print(f"💾 GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            
            # Initialize GPU memory pool
            torch.cuda.empty_cache()
        else:
            print("⚠️ GPU not available, using CPU")
    
    def detect_motion(self, frame):
        try:
            crop_y_upper = self.config.get('detection_zones.detection_area_top', 300)
            crop_y_lower = self.config.get('detection_zones.detection_area_bottom', 590)
            crop_x_left = self.config.get('detection_zones.detection_area_left', 100)
            crop_x_right = self.config.get('detection_zones.detection_area_right', 1820)
            
            crop = frame[crop_y_upper:crop_y_lower, crop_x_left:crop_x_right]
            
            fg_mask = self.bg_subtractor.apply(crop)
            
            blur_size = self.config.get('detection_settings.blur_size', 10)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (blur_size, blur_size))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, kernel)
            
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            detections = []
            min_area = self.config.get('detection_settings.min_area', 500)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if min_area <= area <= 50000:
                    x, y, w, h = cv2.boundingRect(contour)
                    x += crop_x_left
                    y += crop_y_upper
                    detections.append((x, y, w, h))
            
            return detections
            
        except Exception as e:
            print(f"⚠️ Motion detection error: {e}")
            return []
    
    def classify_and_detect_color(self, frame, x, y, w, h):
        try:
            crop = frame[y:y+h, x:x+w]
            if crop.size == 0:
                return "vehicle", "unknown", 0.5
            
            device = 'cuda:0' if self.use_gpu else 'cpu'
            confidence_threshold = self.config.get('detection_settings.confidence_threshold', 0.5)
            
            results = self.yolo_model(crop, device=device, verbose=False)
            
            vehicle_type = "vehicle"
            confidence = 0.5
            detected_objects = []
            
            vehicle_classes = self.config.get('vehicle_settings.vehicle_classes', [])
            ignore_yolo_validation = self.config.get('vehicle_settings.ignore_yolo_validation', False)
            
            highest_conf_object = None
            highest_conf = 0.0
            
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        class_id = int(box.cls.cpu().numpy()[0])
                        conf = float(box.conf.cpu().numpy()[0])
                        
                        if conf >= confidence_threshold:
                            class_name = self.yolo_model.names[class_id]
                            detected_objects.append((class_name, conf))
                            
                            if conf > highest_conf:
                                highest_conf = conf
                                highest_conf_object = class_name
                            
                            if class_name in vehicle_classes:
                                vehicle_type = class_name
                                confidence = conf
                                break
            
            if ignore_yolo_validation and highest_conf_object and vehicle_type == "vehicle" and highest_conf_object not in vehicle_classes:
                vehicle_type = "unknown"
                confidence = highest_conf
                print(f"🔍 YOLO: Detected {highest_conf_object} ({highest_conf:.2f}) - categorized as 'unknown'")
            
            if detected_objects:
                obj_summary = ", ".join([f"{name}({conf:.2f})" for name, conf in detected_objects[:3]])
                print(f"🔍 YOLO: {obj_summary}")
            else:
                if hasattr(self, '_last_no_objects_log'):
                    if time.time() - self._last_no_objects_log > 10:
                        print(f"🔍 YOLO: No objects detected above {confidence_threshold:.2f} confidence")
                        self._last_no_objects_log = time.time()
                else:
                    print(f"🔍 YOLO: No objects detected above {confidence_threshold:.2f} confidence")
                    self._last_no_objects_log = time.time()
            
            vehicle_color = self.color_detector.detect_color(crop)
            
            return vehicle_type, vehicle_color, confidence
            
        except Exception as e:
            print(f"⚠️ YOLO Classification error: {e}")
            return "vehicle", "unknown", 0.3
    
    def update_tracks(self, detections, timestamp):
        current_tracks = {}
        
        for x, y, w, h in detections:
            center_x = x + w/2
            center_y = y + h/2
            
            # Find closest track
            best_match = None
            min_distance = float('inf')
            
            for track_id, track in self.tracks.items():
                distance = math.sqrt((center_x - track.current_x)**2 + 
                                   (center_y - track.current_y)**2)
                
                if distance < min_distance and distance < 100:
                    min_distance = distance
                    best_match = track_id
            
            if best_match:
                track = self.tracks[best_match]
                track.update_position(x, y, w, h, timestamp)
                current_tracks[best_match] = track
            else:
                new_track = VehicleTrack(self.track_id_counter, x, y, w, h, timestamp, self.config)
                current_tracks[self.track_id_counter] = new_track
                self.track_id_counter += 1
        
        self.tracks = current_tracks
    
    def process_tracks(self, frame):
        tracks_to_remove = []
        
        for track_id, track in self.tracks.items():
            track_counter = self.config.get('speed_settings.track_counter', 5)
            if not track.speed_calculated and len(track.positions) >= track_counter:
                if track.calculate_speed():
                    object_type, object_color, confidence = self.classify_and_detect_color(
                        frame, 
                        int(track.current_x - track.width/2),
                        int(track.current_y - track.height/2),
                        int(track.width),
                        int(track.height)
                    )
                    track.vehicle_type = object_type
                    track.vehicle_color = object_color
                    track.confidence = confidence
                    
                    # Log moving vehicle - ADD DEBUG INFO
                    print(f"🔍 Track {track_id}: speed_calc={track.speed_calculated}, track_len={abs(track.current_x - track.start_x):.1f}px, crossed={track.crossed_line}, direction={track.direction}")
                    
                    # Check if YOLO validation is required
                    ignore_yolo_validation = self.config.get('vehicle_settings.ignore_yolo_validation', False)
                    
                    if ignore_yolo_validation:
                        # Log all moving objects regardless of YOLO validation
                        # Objects not in vehicle classes are categorized as "other"
                        print(f"✅ LOGGING ALL MOVING OBJECTS: {track.direction} {track.vehicle_color} {track.vehicle_type}")
                        should_log = True
                    else:
                        # Use YOLO validation
                        require_yolo_validation = self.config.get('detection_settings.require_yolo_validation', True)
                        accept_generic_vehicle = self.config.get('detection_settings.accept_generic_vehicle', True)
                        vehicle_classes = self.config.get('vehicle_settings.vehicle_classes', [])
                        
                        should_log = True
                        if require_yolo_validation:
                            # Check if object is in our vehicle classes OR is generic "vehicle" (if enabled)
                            valid_object = object_type in vehicle_classes
                            if not valid_object and accept_generic_vehicle and object_type == 'vehicle':
                                valid_object = True
                            
                            should_log = valid_object and confidence > 0.3
                            if not should_log:
                                print(f"❌ NOT LOGGING: YOLO validation failed - {object_type} (conf: {confidence:.2f}) not in vehicle classes or confidence too low")
                            else:
                                print(f"✅ YOLO VALIDATED: {track.direction} {track.vehicle_color} {track.vehicle_type} (conf: {confidence:.2f})")
                        else:
                            print(f"✅ LOGGING WITHOUT YOLO VALIDATION: {track.direction} {track.vehicle_color} {track.vehicle_type}")
                    
                    if should_log:
                        self.log_vehicle_detection(track, frame)
                        self.stats['moving_logged'] += 1
                        
                        if track.direction == 'L2R':
                            self.stats['l2r_count'] += 1
                        else:
                            self.stats['r2l_count'] += 1
                    
                    tracks_to_remove.append(track_id)
            
            elif (time.time() - track.start_time) > self.config.get('speed_settings.max_time_diff', 10):
                if not track.speed_calculated:
                    self.stats['stationary_ignored'] += 1
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            if track_id in self.tracks:
                del self.tracks[track_id]
    
    def log_vehicle_detection(self, track, frame):
        print(f"🔍 log_vehicle_detection called for track {track.track_id}")
        timestamp = datetime.now()
        speed_mph = self.config.get('speed_settings.speed_mph', False)
        speed_display = track.speed_mph if speed_mph else track.speed_kmh
        speed_unit = "mph" if speed_mph else "km/h"
        
        image_filename = ""
        
        # Check if image saving is enabled
        save_images = self.config.get('output_settings.save_images', True)
        if save_images:
            # Save image (fix filename for Windows compatibility)
            speed_str = f"{speed_display:.1f}".replace(".", "_")
            unit_str = speed_unit.replace("/", "_per_")  # km/h -> km_per_h
            image_filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{track.direction}_{track.vehicle_color}_{track.vehicle_type}_{speed_str}{unit_str}.jpg"
            image_path = os.path.join(self.output_dir, image_filename)
            
            # Draw annotations on image
            annotated = frame.copy()
            x = int(track.current_x - track.width/2)
            y = int(track.current_y - track.height/2)
            w = int(track.width)
            h = int(track.height)
            
            # Vehicle bounding box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 3)
            
            # Speed text
            cv2.putText(annotated, f"{speed_display:.1f} {speed_unit}", 
                       (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            
            # Object info
            info_text = f"{track.direction} {track.vehicle_color} {track.vehicle_type}"
            cv2.putText(annotated, info_text, (x, y + h + 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # GPU info
            if self.use_gpu:
                gpu_text = f"GPU: {torch.cuda.get_device_name(0)}"
                cv2.putText(annotated, gpu_text, (10, frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            # Save image with configurable quality
            try:
                image_quality = self.config.get('output_settings.image_quality', 95)
                success = cv2.imwrite(image_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, image_quality])
                if success:
                    print(f"✅ Image saved: {image_filename}")
                else:
                    print(f"❌ Failed to save image: {image_filename}")
            except Exception as e:
                print(f"❌ Error saving image {image_filename}: {e}")
        
        # Log to CSV with correct column order to match headers
        row = [
            timestamp.isoformat(),
            track.vehicle_type,
            track.vehicle_color,
            track.direction,
            round(track.speed_kmh, 1),
            round(track.speed_mph, 1),
            round(track.confidence, 2),
            image_filename,  # Will be empty string if save_images is False
            False  # removed column - default to False for new entries
        ]
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f"🎯 {timestamp.strftime('%H:%M:%S')} | {track.direction} | "
              f"{track.vehicle_color} {track.vehicle_type} | {speed_display:.1f} {speed_unit} | GPU: {self.use_gpu}")
    
    def draw_overlay(self, frame):
        overlay = frame.copy()
        
        # Get detection area from config
        crop_y_upper = self.config.get('detection_zones.detection_area_top', 300)
        crop_y_lower = self.config.get('detection_zones.detection_area_bottom', 590)
        crop_x_left = self.config.get('detection_zones.detection_area_left', 100)
        crop_x_right = self.config.get('detection_zones.detection_area_right', 1820)
        l2r_line_x = self.config.get('detection_zones.l2r_line_x', 400)
        r2l_line_x = self.config.get('detection_zones.r2l_line_x', 1400)
        
        # Draw detection area
        cv2.rectangle(overlay, 
                     (crop_x_left, crop_y_upper),
                     (crop_x_right, crop_y_lower),
                     (255, 255, 0), 2)
        
        # Draw tracking lines
        cv2.line(overlay, (l2r_line_x, crop_y_upper), (l2r_line_x, crop_y_lower), (0, 255, 255), 3)
        cv2.line(overlay, (r2l_line_x, crop_y_upper), (r2l_line_x, crop_y_lower), (255, 0, 255), 3)
        
        cv2.putText(overlay, "L2R", (l2r_line_x + 5, crop_y_upper + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(overlay, "R2L", (r2l_line_x + 5, crop_y_upper + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        
        # Draw current tracks
        for track in self.tracks.values():
            x = int(track.current_x - track.width/2)
            y = int(track.current_y - track.height/2)
            w = int(track.width)
            h = int(track.height)
            
            color = (0, 255, 255) if track.direction == 'L2R' else (255, 0, 255)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
        
        # Stats with GPU info
        stats_text = f"Objects: {self.stats['moving_logged']} | L2R: {self.stats['l2r_count']} | R2L: {self.stats['r2l_count']} | GPU: {self.use_gpu}"
        cv2.putText(overlay, stats_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Frame buffer stats
        buffer_stats = self.frame_buffer.get_stats()
        buffer_text = f"Frames: {buffer_stats['total_frames']} | Errors: {buffer_stats['error_count']} | Error Rate: {buffer_stats['error_rate']:.1f}%"
        cv2.putText(overlay, buffer_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return overlay
    
    def process_frame(self, frame):
        try:
            # Add overlay with detection zones and stats
            processed_frame = self.draw_overlay(frame)
            
            # Store latest frame for web streaming
            self.latest_frame = processed_frame.copy()
            
            return processed_frame
        except Exception as e:
            print(f"⚠️ Frame processing error: {e}")
            return frame
    
    def get_latest_frame(self):
        if hasattr(self, 'latest_frame'):
            return self.latest_frame
        return None
    
    def stop(self):
        print("🛑 Stopping speed camera...")
        self.running = False
        if hasattr(self, 'rtsp_decoder'):
            self.rtsp_decoder.stop()
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        if self.use_gpu:
            torch.cuda.empty_cache()
        print("✅ Speed camera stopped")
    
    def process_stream(self):
        print("🚀 Starting GPU-accelerated processing...")
        
        # Start RTSP decoder
        self.rtsp_decoder.start()
        
        # Wait for first frame
        print("⏳ Waiting for first frame...")
        frame = None
        for _ in range(50):  # Wait up to 5 seconds
            frame = self.frame_buffer.get(timeout=0.1)
            if frame is not None:
                break
        
        if frame is None:
            print("❌ No frames received!")
            return
        
        print("✅ First frame received! Starting detection...")
        print("🟡 Yellow line: L2R | 🟣 Magenta line: R2L")
        
        # Check logging mode
        ignore_yolo_validation = self.config.get('vehicle_settings.ignore_yolo_validation', False)
        if ignore_yolo_validation:
            print("📊 ALL moving objects will be logged (unknown objects categorized as 'unknown')")
        else:
            print("📊 Only moving objects (vehicles/pedestrians/bicycles) will be logged")
        
        print("🚀 GPU acceleration enabled" if self.use_gpu else "💻 CPU processing")
        
        try:
            while self.running:
                frame = self.frame_buffer.get(timeout=1.0)
                if frame is None:
                    continue
                
                self.frame_count += 1
                self.stats['frames_processed'] += 1
                timestamp = time.time()
                
                # GPU memory management
                if self.use_gpu and self.frame_count % 100 == 0:
                    torch.cuda.empty_cache()
                
                # Detect motion with GPU acceleration
                detections = self.detect_motion(frame)
                
                # Update tracks
                self.update_tracks(detections, timestamp)
                
                # Process for speed
                self.process_tracks(frame)
                
                # Store latest frame for web streaming
                self.latest_frame = self.draw_overlay(frame.copy())
                
                # Update stats every 1000 frames
                if self.frame_count % 1000 == 0:
                    print(f"📊 Processed {self.frame_count} frames | "
                          f"Error rate: {self.frame_buffer.get_stats()['error_rate']:.1f}% | "
                          f"Moving objects: {self.stats['moving_logged']}")
                
                time.sleep(0.01)  # Small delay to prevent CPU overload
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        finally:
            self.rtsp_decoder.stop()
            self.executor.shutdown(wait=True)
            
            if self.use_gpu:
                torch.cuda.empty_cache()
            
            print(f"📊 Final Stats:")
            print(f"   Frames processed: {self.stats['frames_processed']}")
            print(f"   Moving objects logged: {self.stats['moving_logged']}")
            print(f"   Stationary ignored: {self.stats['stationary_ignored']}")
            print(f"   L2R: {self.stats['l2r_count']} | R2L: {self.stats['r2l_count']}")
            
            buffer_stats = self.frame_buffer.get_stats()
            print(f"   Total frames: {buffer_stats['total_frames']}")
            print(f"   Decode errors: {buffer_stats['error_count']}")
            print(f"   Error rate: {buffer_stats['error_rate']:.1f}%")
    
    def start(self):
        self.running = True
        self.process_stream()

def main():
    print("🚗 Speed Camera System")
    print("=" * 40)
    
    if torch.cuda.is_available():
        print(f"🚀 GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("💻 CPU Processing")
    
    print("=" * 40)
    
    camera = SpeedCamera()
    camera.start()

if __name__ == "__main__":
    main()
