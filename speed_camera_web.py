#!/usr/bin/env python3

from flask import Flask, request, jsonify, Response, send_from_directory, send_file
import json
import threading
import time
import os
import cv2
import logging
import subprocess
import glob
from datetime import datetime, timedelta
from speed_camera import SpeedCamera
from config_manager import config_manager
import io
import base64
from collections import deque
import csv
from io import StringIO
import numpy as np
import psutil

app = Flask(__name__)

# Global variables
speed_camera = None
camera_thread = None
running = False
console_logs = []
console_lock = threading.Lock()
system_logs = deque(maxlen=500)

# Create required directories
os.makedirs('detections', exist_ok=True)  # Only create detections folder

# Add startup time tracking
startup_time = time.time()

class WebConsoleHandler(logging.Handler):
    def emit(self, record):
        try:
            # Always filter out HTTP requests (too noisy)
            if any(skip in record.getMessage() for skip in [
                'GET /api/', 'POST /api/', '200 -', '404 -', 
                'werkzeug', 'INFO:werkzeug'
            ]):
                return
                
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.name
            }
            
            with console_lock:
                console_logs.append(log_entry)
                max_logs = 1000  # Always use larger log buffer
                if len(console_logs) > max_logs:
                    console_logs.pop(0)
        except:
            pass

# Setup enhanced logging to capture everything
logging.basicConfig(
    level=logging.DEBUG,  # Capture all levels
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Console only, no file logging
    ]
)

web_handler = WebConsoleHandler()
web_handler.setLevel(logging.DEBUG)  # Capture debug messages too

# Add handler to root logger to capture all logs
root_logger = logging.getLogger()
root_logger.addHandler(web_handler)

# Also capture print statements from speed camera and other modules
import sys

class PrintCapture:
    def __init__(self, stream_name='stdout'):
        self.terminal = sys.stdout if stream_name == 'stdout' else sys.stderr
        self.stream_name = stream_name
        
    def write(self, message):
        self.terminal.write(message)
        if message.strip():
            # Determine log level from message content
            level = 'INFO'
            if any(keyword in message for keyword in ['ERROR', 'Error', 'Failed', 'failed']):
                level = 'ERROR'
            elif any(keyword in message for keyword in ['WARNING', 'Warning']):
                level = 'WARNING'
            elif any(keyword in message for keyword in ['DEBUG', 'Debug']):
                level = 'DEBUG'
            elif any(keyword in message for keyword in ['INFO', 'Info', 'Starting', 'Stopping']):
                level = 'INFO'
            
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'message': message.strip(),
                'module': f'speed_camera_{self.stream_name}'
            }
            with console_lock:
                console_logs.append(log_entry)
                max_logs = 1000
                if len(console_logs) > max_logs:
                    console_logs.pop(0)
    
    def flush(self):
        self.terminal.flush()

class StderrCapture:
    def __init__(self):
        self.terminal = sys.stderr
        
    def write(self, message):
        self.terminal.write(message)
        if message.strip():
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': 'ERROR',
                'message': message.strip(),
                'module': 'speed_camera_stderr'
            }
            with console_lock:
                console_logs.append(log_entry)
                max_logs = 1000  # Always use larger log buffer
                if len(console_logs) > max_logs:
                    console_logs.pop(0)
    
    def flush(self):
        self.terminal.flush()

# Redirect stdout and stderr to capture all output
sys.stdout = PrintCapture('stdout')
sys.stderr = StderrCapture()



@app.route('/')
def dashboard():
    return send_from_directory('frontend', 'index.html')

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('frontend/css', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('frontend/js', filename)

@app.route('/components/<path:filename>')
def serve_components(filename):
    return send_from_directory('frontend/components', filename)

@app.route('/frontend/<path:filename>')
def frontend_files(filename):
    return send_from_directory('frontend', filename)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(config_manager.get_all())

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({'status': 'error', 'message': 'No configuration data provided'}), 400
        
        # Update each section
        for section, data in new_config.items():
            if section.startswith('_'):  # Skip metadata
                continue
            config_manager.update_section(section, data)
        
        # Save the configuration
        if config_manager.save_config():
            return jsonify({'status': 'success', 'message': 'Configuration updated successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to save configuration'}), 500
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/status')
def get_status():
    global speed_camera, running, startup_time
    
    status = {
        'running': running,
        'camera_connected': False,
        'violations_count': 0,
        'uptime': 0,
        'memory_usage': 0,
        'frames_processed': 0,
        'images_size': "0 MB"
    }
    
    # Get system stats
    try:
        status['memory_usage'] = psutil.virtual_memory().percent
        
        # Calculate total size of saved images instead of disk usage
        detections_dir = 'detections'
        total_size = 0
        if os.path.exists(detections_dir):
            for filename in os.listdir(detections_dir):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    file_path = os.path.join(detections_dir, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
        
        # Convert to MB or GB
        if total_size > 1024 * 1024 * 1024:  # > 1GB
            status['images_size'] = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
        else:
            status['images_size'] = f"{total_size / (1024 * 1024):.1f} MB"
    except:
        status['images_size'] = "0 MB"
    
    # Calculate uptime in seconds since startup
    status['uptime'] = int(time.time() - startup_time)
    
    # Check camera connection more accurately
    if speed_camera:
        try:
            # Get basic stats without error rate
            stats = speed_camera.frame_buffer.get_stats()
            status['total_frames'] = stats.get('total_frames', 0)
            # Camera is connected if we have processed frames
            status['camera_connected'] = stats.get('total_frames', 0) > 0
            # Update running status based on actual camera state
            if hasattr(speed_camera, 'running'):
                running = speed_camera.running
                status['running'] = running
        except:
            status['camera_connected'] = False
    else:
        status['camera_connected'] = False
    
    # Get speed camera stats if available
    if speed_camera and hasattr(speed_camera, 'stats'):
        status['violations_count'] = speed_camera.stats.get('moving_logged', 0)
        status['frames_processed'] = speed_camera.stats.get('frames_processed', 0)
    
    # Check if CSV file exists and count detections
    csv_file = 'object_detections.csv'
    csv_path = os.path.join('detections', csv_file)
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r') as f:
                lines = f.readlines()
                # Skip header line
                status['violations_count'] = max(len(lines) - 1, 0) if len(lines) > 1 else 0
        except:
            pass
    
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def start_camera():
    global speed_camera, camera_thread, running
    
    if running:
        return jsonify({'status': 'error', 'message': 'Camera already running'})
    
    try:
        # Create new speed camera instance
        speed_camera = SpeedCamera()
        running = True
        
        def run_camera():
            try:
                speed_camera.start()
            except Exception as e:
                logging.error(f"Camera error: {str(e)}")
                global running
                running = False
        
        camera_thread = threading.Thread(target=run_camera)
        camera_thread.daemon = True
        camera_thread.start()
        
        logging.info("Speed camera started via web interface")
        return jsonify({'status': 'success', 'message': 'Speed camera started'})
    except Exception as e:
        running = False
        logging.error(f"Failed to start camera: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_camera():
    global speed_camera, running
    
    if not running:
        return jsonify({'status': 'error', 'message': 'Camera not running'})
    
    try:
        running = False
        if speed_camera:
            speed_camera.running = False
        
        logging.info("Speed camera stopped")
        return jsonify({'status': 'success', 'message': 'Speed camera stopped'})
    except Exception as e:
        logging.error(f"Failed to stop camera: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/detections')
def get_detections():
    try:
        # Get query parameters
        time_filter = request.args.get('time_filter', 'all')
        limit = request.args.get('limit', None)
        format_type = request.args.get('format', 'json')
        violations_only = request.args.get('violations_only', 'false').lower() == 'true'
        type_filter = request.args.get('type', None)
        
        detections = []
        csv_file = 'detections/object_detections.csv'
        
        # Get speed limit from config for violation filtering
        speed_limit = config_manager.get('speed_settings.speed_limit_kmh', 50)
        
        if os.path.exists(csv_file):
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        # Skip removed entries
                        is_removed = row.get('removed', 'False').lower() == 'true'
                        if is_removed:
                            continue
                        
                        # Parse timestamp
                        timestamp = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                        
                        # Apply time filter
                        now = datetime.now()
                        if time_filter == '1h' and (now - timestamp).total_seconds() > 3600:
                            continue
                        elif time_filter == '3h' and (now - timestamp).total_seconds() > 10800:
                            continue
                        elif time_filter == '1d' and (now - timestamp).total_seconds() > 86400:
                            continue
                        elif time_filter == '1w' and (now - timestamp).total_seconds() > 604800:
                            continue
                        
                        speed_kmh = float(row.get('speed_kmh', 0))
                        is_violation = speed_kmh > speed_limit
                        
                        detection = {
                            'timestamp': row['timestamp'],
                            'direction': row.get('direction', 'Unknown'),
                            'speed_kmh': speed_kmh,
                            'speed_mph': float(row.get('speed_mph', 0)),
                            'object_type': row.get('object_type', 'vehicle'),
                            'object_color': row.get('object_color', 'unknown'),
                            'confidence': float(row.get('confidence', 0)),
                            'image_file': row.get('image_file', ''),
                            'has_image': bool(row.get('image_file', '').strip()),
                            'is_violation': is_violation,
                            'speed_limit': speed_limit
                        }
                        
                        # Apply violations filter if requested
                        if violations_only and not is_violation:
                            continue
                        
                        # Apply type filter if requested
                        if type_filter and detection['object_type'] != type_filter:
                            continue
                            
                        detections.append(detection)
                    except (ValueError, KeyError) as e:
                        continue
        
        # Sort by timestamp (newest first)
        detections.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Apply limit
        if limit and limit != 'all':
            try:
                limit_num = int(limit)
                detections = detections[:limit_num]
            except ValueError:
                pass
        
        if format_type == 'csv':
            # Return CSV format
            if not detections:
                return "No data available", 200, {'Content-Type': 'text/plain'}
            
            output = StringIO()
            fieldnames = detections[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detections)
            
            filename_prefix = 'violations' if violations_only else 'detections'
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename={filename_prefix}_{time_filter}.csv'
            }
        
        return jsonify(detections)
        
    except Exception as e:
        logging.error(f"Error getting detections: {e}")
        return jsonify({'error': str(e)}), 500

# Keep old violations endpoint for backward compatibility
@app.route('/api/violations')
def get_violations():
    # Add violations_only=true to the request args
    from flask import request
    args = dict(request.args)
    args['violations_only'] = 'true'
    
    # Redirect to detections endpoint with violations filter
    from urllib.parse import urlencode
    query_string = urlencode(args)
    
    # Call detections endpoint directly
    request.args = request.args.copy()
    request.args = type('MockArgs', (), args)()
    return get_detections()

@app.route('/api/console')
def get_console():
    try:
        with console_lock:
            logs = console_logs.copy()
        
        # Get filter parameters
        level_filter = request.args.get('level', None)
        module_filter = request.args.get('module', None)
        limit = request.args.get('limit', '100')
        
        # Apply filters
        filtered_logs = logs
        
        if level_filter:
            filtered_logs = [log for log in filtered_logs if log.get('level', '').upper() == level_filter.upper()]
        
        if module_filter:
            filtered_logs = [log for log in filtered_logs if module_filter.lower() in log.get('module', '').lower()]
        
        # Apply limit
        try:
            limit_num = int(limit)
            filtered_logs = filtered_logs[-limit_num:] if len(filtered_logs) > limit_num else filtered_logs
        except ValueError:
            filtered_logs = filtered_logs[-100:]  # Default to last 100
        
        # Add debug info
        debug_enabled = config_manager.get('debug_settings.verbose_logging', False)
        
        return jsonify({
            'logs': filtered_logs,
            'total_count': len(logs),
            'filtered_count': len(filtered_logs),
            'debug_enabled': debug_enabled,
            'timestamp': datetime.now().isoformat(),
            'available_levels': list(set(log.get('level', 'INFO') for log in logs)),
            'available_modules': list(set(log.get('module', 'unknown') for log in logs))
        })
    except Exception as e:
        error_log = {
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'message': f'Error getting console logs: {str(e)}',
            'module': 'web_server'
        }
        return jsonify({
            'logs': [error_log],
            'total_count': 1,
            'filtered_count': 1,
            'debug_enabled': False,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        })



@app.route('/api/system/info')
def system_info():
    info = {
        'python_version': '',
        'opencv_version': '',
        'torch_version': '',
        'platform': '',
        'cpu_count': 0,
        'memory_total': 0
    }
    
    try:
        import sys, platform, psutil
        info['python_version'] = sys.version
        info['platform'] = platform.platform()
        info['cpu_count'] = psutil.cpu_count()
        info['memory_total'] = round(psutil.virtual_memory().total / (1024**3), 2)
        
        try:
            import cv2
            info['opencv_version'] = cv2.__version__
        except:
            pass
            
        try:
            import torch
            info['torch_version'] = torch.__version__
        except:
            pass
    except:
        pass
    
    return jsonify(info)

@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory('detections', filename)

@app.route('/api/images')
def get_images():
    """Get all available images from detections folder"""
    images = []
    
    try:
        output_dir = 'detections'
        
        if os.path.exists(output_dir):
            # Get all image files
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
            for ext in image_extensions:
                image_files = glob.glob(os.path.join(output_dir, ext))
                for img_file in image_files:
                    stat = os.stat(img_file)
                    images.append({
                        'filename': os.path.basename(img_file),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'path': f"/images/{os.path.basename(img_file)}"
                    })
            
            # Sort by modification time (newest first)
            images.sort(key=lambda x: x['modified'], reverse=True)
    
    except Exception as e:
        logging.error(f"Error getting images: {e}")
    
    return jsonify(images)

@app.route('/api/files/download/<filename>')
def download_file(filename):
    """Download a file"""
    try:
        detections_dir = 'detections'  # Use detections folder
        file_path = os.path.join(detections_dir, filename)
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/cleanup', methods=['POST'])
def cleanup_old_files():
    """Clean up old detection files"""
    try:
        detections_dir = 'detections'
        
        if not os.path.exists(detections_dir):
            return jsonify({"status": "error", "message": "Detections directory not found"})
        
        # Use default 30 days retention
        retention_days = 30
        cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
        
        deleted_count = 0
        total_size = 0
        
        for filename in os.listdir(detections_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(detections_dir, filename)
                if os.path.getmtime(file_path) < cutoff_time:
                    file_size = os.path.getsize(file_path)
                    # Mark CSV entry as removed before deleting the file
                    mark_csv_entry_as_removed(filename)
                    os.remove(file_path)
                    deleted_count += 1
                    total_size += file_size
        
        size_mb = total_size / (1024 * 1024)
        message = f"Cleaned up {deleted_count} old files, freed {size_mb:.1f} MB of space."
        
        return jsonify({"status": "success", "message": message, "deleted_count": deleted_count, "size_freed_mb": round(size_mb, 1)})
        
    except Exception as e:
        error_msg = f"Error during cleanup: {str(e)}"
        logging.error(error_msg)
        return jsonify({"status": "error", "message": error_msg})

def mark_csv_entry_as_removed(image_filename):
    """Mark a CSV entry as removed based on image filename"""
    try:
        csv_file = 'detections/object_detections.csv'
        if not os.path.exists(csv_file):
            return False
        
        # Read all rows
        rows = []
        updated = False
        
        with open(csv_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            
            # Add 'removed' column if it doesn't exist
            if 'removed' not in fieldnames:
                fieldnames = list(fieldnames) + ['removed']
            
            for row in reader:
                # Add 'removed' column if missing
                if 'removed' not in row:
                    row['removed'] = 'False'
                
                # Mark as removed if this is the file being deleted
                if row.get('image_file') == image_filename:
                    row['removed'] = 'True'
                    updated = True
                
                rows.append(row)
        
        # Write back to file if we made changes
        if updated:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            logging.info(f"Marked CSV entry as removed for image: {image_filename}")
            return True
        
        return False
        
    except Exception as e:
        logging.error(f"Error marking CSV entry as removed: {e}")
        return False

@app.route('/api/files/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file and mark CSV entry as removed"""
    try:
        detections_dir = 'detections'  # Use detections folder
        file_path = os.path.join(detections_dir, filename)
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Mark CSV entry as removed before deleting the file
            mark_csv_entry_as_removed(filename)
            
            # Delete the actual file
            os.remove(file_path)
            
            return jsonify({'success': True, 'message': f'File {filename} deleted and marked as removed in CSV'})
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/execute', methods=['POST'])
def execute_command():
    """Execute system commands (be careful!)"""
    try:
        command = request.json.get('command', '')
        if not command:
            return jsonify({'status': 'error', 'message': 'No command provided'})
        
        # Security: Only allow safe commands
        safe_commands = ['ls', 'ps', 'df', 'free', 'uptime', 'whoami']
        cmd_parts = command.split()
        if cmd_parts[0] not in safe_commands:
            return jsonify({'status': 'error', 'message': 'Command not allowed'})
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        
        return jsonify({
            'status': 'success',
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config/export', methods=['POST'])
def export_config():
    """Export configuration to file"""
    try:
        filename = request.json.get('filename', 'config_backup.json')
        if config_manager.export_config(filename):
            return jsonify({'status': 'success', 'message': f'Configuration exported to {filename}'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to export configuration'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config/import', methods=['POST'])
def import_config():
    """Import configuration from file"""
    try:
        filename = request.json.get('filename', 'config_backup.json')
        if config_manager.import_config(filename):
            return jsonify({'status': 'success', 'message': f'Configuration imported from {filename}'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to import configuration'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults"""
    try:
        config_manager.reset_to_defaults()
        return jsonify({'status': 'success', 'message': 'Configuration reset to defaults'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/config/validate', methods=['GET'])
def validate_config():
    """Validate current configuration"""
    try:
        errors = config_manager.validate_config()
        if errors:
            return jsonify({'status': 'warning', 'errors': errors})
        else:
            return jsonify({'status': 'success', 'message': 'Configuration is valid'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/analytics')
def get_analytics():
    """Get analytics data from CSV for charts with time filtering"""
    # Get time filter parameter
    time_filter = request.args.get('time_filter', 'all')  # all, hour, 3hour, day, week
    
    analytics = {
        'speed_over_time': [],
        'speed_distribution': {},
        'vehicle_types': {},
        'vehicle_colors': {},
        'directions': {},
        'hourly_activity': {},
        'stats': {},
        'time_filter': time_filter
    }
    
    try:
        csv_file = 'detections/object_detections.csv'  # Use detections folder
        
        if not os.path.exists(csv_file):
            return jsonify({'status': 'error', 'message': 'Detections CSV file not found'}), 404
        
        from collections import defaultdict
        
        speeds = []
        hourly_counts = defaultdict(int)
        minute_counts = defaultdict(int)  # For finer granularity
        all_timestamps = []
        
        # Calculate time cutoff based on filter
        now = datetime.now()
        cutoff_time = None
        if time_filter == 'hour':
            cutoff_time = now - timedelta(hours=1)
        elif time_filter == '3hour':
            cutoff_time = now - timedelta(hours=3)
        elif time_filter == 'day':
            cutoff_time = now - timedelta(days=1)
        elif time_filter == 'week':
            cutoff_time = now - timedelta(weeks=1)
        
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Skip removed entries
                    is_removed = row.get('removed', 'False').lower() == 'true'
                    if is_removed:
                        continue
                    
                    # Parse data
                    speed = float(row.get('speed_kmh', 0))
                    obj_type = row.get('object_type', 'unknown').lower()
                    obj_color = row.get('object_color', 'unknown').lower()
                    direction = row.get('direction', 'unknown')
                    timestamp = row.get('timestamp', '')
                    
                    # Apply time filtering
                    if cutoff_time and timestamp:
                        try:
                            row_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            if row_time < cutoff_time:
                                continue  # Skip this row
                        except:
                            continue  # Skip if timestamp parsing fails
                    
                    speeds.append(speed)
                    all_timestamps.append(timestamp)
                    
                    # Store speed data with parsed timestamp for averaging
                    if timestamp:
                        try:
                            row_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            analytics['speed_over_time'].append({
                                'timestamp': timestamp,
                                'datetime': row_time,
                                'speed': speed,
                                'type': obj_type,
                                'direction': direction
                            })
                        except:
                            pass
                    
                    # Vehicle types
                    if obj_type in analytics['vehicle_types']:
                        analytics['vehicle_types'][obj_type] += 1
                    else:
                        analytics['vehicle_types'][obj_type] = 1
                    
                    # Vehicle colors
                    if obj_color in analytics['vehicle_colors']:
                        analytics['vehicle_colors'][obj_color] += 1
                    else:
                        analytics['vehicle_colors'][obj_color] = 1
                    
                    # Directions
                    if direction in analytics['directions']:
                        analytics['directions'][direction] += 1
                    else:
                        analytics['directions'][direction] = 1
                    
                    # Time-based activity tracking
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            hour = dt.hour
                            hourly_counts[hour] += 1
                            
                            # For minute-level granularity
                            minute_key = f"{hour:02d}:{dt.minute:02d}"
                            minute_counts[minute_key] += 1
                        except:
                            pass
                    
                except Exception as e:
                    logging.warning(f"Error processing row: {e}")
                    continue
        
        # Calculate average speeds over time intervals
        if analytics['speed_over_time']:
            # Determine number of data points based on time filter
            data_points = 20  # Default for 'all'
            if time_filter == 'hour':
                data_points = 60  # Every minute
            elif time_filter == '3hour':
                data_points = 36  # Every 5 minutes
            elif time_filter == 'day':
                data_points = 24  # Every hour
            elif time_filter == 'week':
                data_points = 14  # Every 12 hours
            
            # Sort by datetime
            speed_data = sorted(analytics['speed_over_time'], key=lambda x: x['datetime'])
            
            if len(speed_data) > 1:
                # Calculate time intervals
                start_time = speed_data[0]['datetime']
                end_time = speed_data[-1]['datetime']
                total_duration = (end_time - start_time).total_seconds()
                
                if total_duration > 0:
                    interval_seconds = total_duration / data_points
                    
                    # Group data into intervals and calculate averages
                    averaged_data = []
                    for i in range(data_points):
                        interval_start = start_time + timedelta(seconds=i * interval_seconds)
                        interval_end = start_time + timedelta(seconds=(i + 1) * interval_seconds)
                        
                        # Find all speeds in this interval
                        interval_speeds = []
                        interval_types = []
                        interval_directions = []
                        
                        for data_point in speed_data:
                            if interval_start <= data_point['datetime'] < interval_end:
                                interval_speeds.append(data_point['speed'])
                                interval_types.append(data_point['type'])
                                interval_directions.append(data_point['direction'])
                        
                        # Calculate average for this interval
                        if interval_speeds:
                            avg_speed = sum(interval_speeds) / len(interval_speeds)
                            # Use most common type and direction in interval
                            most_common_type = max(set(interval_types), key=interval_types.count) if interval_types else 'unknown'
                            most_common_direction = max(set(interval_directions), key=interval_directions.count) if interval_directions else 'unknown'
                            
                            averaged_data.append({
                                'timestamp': interval_start.isoformat(),
                                'speed': round(avg_speed, 1),
                                'type': most_common_type,
                                'direction': most_common_direction,
                                'count': len(interval_speeds)  # Number of detections in this interval
                            })
                    
                    # Replace individual data points with averaged data
                    analytics['speed_over_time'] = averaged_data
                else:
                    # If all data is from same time, just return first point
                    analytics['speed_over_time'] = [{
                        'timestamp': speed_data[0]['timestamp'],
                        'speed': speed_data[0]['speed'],
                        'type': speed_data[0]['type'],
                        'direction': speed_data[0]['direction'],
                        'count': 1
                    }]
            else:
                # Single data point
                if speed_data:
                    analytics['speed_over_time'] = [{
                        'timestamp': speed_data[0]['timestamp'],
                        'speed': speed_data[0]['speed'],
                        'type': speed_data[0]['type'],
                        'direction': speed_data[0]['direction'],
                        'count': 1
                    }]
        
        # Speed distribution (bins)
        if speeds:
            speed_bins = {}
            for speed in speeds:
                bin_key = f"{int(speed//10)*10}-{int(speed//10)*10+9}"
                if bin_key in speed_bins:
                    speed_bins[bin_key] += 1
                else:
                    speed_bins[bin_key] = 1
            analytics['speed_distribution'] = speed_bins
        
        # Time-based activity based on filter
        if time_filter == 'hour':
            # Show 5-minute intervals for last hour
            now_minute = now.minute
            current_hour = now.hour
            analytics['hourly_activity'] = {}
            
            for i in range(12):  # 12 * 5 minutes = 60 minutes
                minute_start = (now_minute - (i * 5)) % 60
                hour_adj = current_hour
                if now_minute - (i * 5) < 0:
                    hour_adj = (current_hour - 1) % 24
                
                key = f"{hour_adj:02d}:{minute_start:02d}"
                label = f"{hour_adj:02d}:{minute_start:02d}"
                
                # Count detections in this 5-minute window
                count = 0
                for minute_key, minute_count in minute_counts.items():
                    try:
                        m_hour, m_minute = map(int, minute_key.split(':'))
                        if m_hour == hour_adj and abs(m_minute - minute_start) < 5:
                            count += minute_count
                    except:
                        continue
                
                analytics['hourly_activity'][label] = count
        elif time_filter == '3hour':
            # Show 15-minute intervals for last 3 hours
            analytics['hourly_activity'] = {}
            current_hour = now.hour
            current_minute = now.minute
            
            for i in range(12):  # 12 * 15 minutes = 3 hours
                minutes_back = i * 15
                target_minute = (current_minute - minutes_back) % 60
                hour_back = minutes_back // 60
                if current_minute - minutes_back < 0:
                    hour_back += 1
                target_hour = (current_hour - hour_back) % 24
                
                label = f"{target_hour:02d}:{target_minute:02d}"
                
                # Count detections in this 15-minute window
                count = 0
                for minute_key, minute_count in minute_counts.items():
                    try:
                        m_hour, m_minute = map(int, minute_key.split(':'))
                        if m_hour == target_hour and abs(m_minute - target_minute) < 15:
                            count += minute_count
                    except:
                        continue
                
                analytics['hourly_activity'][label] = count
        else:
            # Default hourly activity (fill missing hours)
            for hour in range(24):
                analytics['hourly_activity'][str(hour)] = hourly_counts.get(hour, 0)
        
        # Calculate totals and rates based on actual data
        total_detections = len(speeds)
        cars_per_hour = 0
        cars_per_day = total_detections  # Total cars detected
        cars_per_week = total_detections  # Total cars detected
        
        if all_timestamps and total_detections > 0:
            try:
                # Parse timestamps
                timestamps_dt = []
                for ts in all_timestamps:
                    try:
                        timestamps_dt.append(datetime.fromisoformat(ts.replace('Z', '+00:00')))
                    except:
                        continue
                
                if timestamps_dt:
                    # Calculate actual time span
                    time_span_seconds = (max(timestamps_dt) - min(timestamps_dt)).total_seconds()
                    time_span_hours = time_span_seconds / 3600
                    time_span_days = time_span_seconds / 86400
                    time_span_weeks = time_span_seconds / 604800
                    
                    # Only calculate rate for hours, show totals for day/week
                    if time_span_hours > 0:
                        cars_per_hour = round(total_detections / time_span_hours, 1)
                    
                    # For day/week, show total if time span is less than full period
                    if time_span_days >= 1:
                        cars_per_day = round(total_detections / time_span_days, 1)
                    # else: keep total_detections
                    
                    if time_span_weeks >= 1:
                        cars_per_week = round(total_detections / time_span_weeks, 1)
                    # else: keep total_detections
                        
            except Exception as e:
                logging.warning(f"Error calculating cars per time period: {e}")
        
        # Calculate statistics
        stats = {
            'total_detections': len(speeds),
            'avg_speed': round(sum(speeds) / len(speeds), 1) if speeds else 0,
            'max_speed': max(speeds) if speeds else 0,
            'min_speed': min(speeds) if speeds else 0,
            'violations': len([s for s in speeds if s > 50]),  # Assuming 50 km/h limit
            'most_common_type': max(analytics['vehicle_types'].items(), key=lambda x: x[1])[0] if analytics['vehicle_types'] else 'N/A',
            'most_common_color': max(analytics['vehicle_colors'].items(), key=lambda x: x[1])[0] if analytics['vehicle_colors'] else 'N/A',
            'cars_per_hour': cars_per_hour,
            'cars_per_day': cars_per_day,
            'cars_per_week': cars_per_week
        }
        
        analytics['stats'] = stats
    
    except Exception as e:
        logging.error(f"Error generating analytics: {e}")
    
    return jsonify(analytics)

@app.route('/images/')
def list_images():
    """List all images in detections directory"""
    try:
        detections_dir = 'detections'
        if not os.path.exists(detections_dir):
            return "<h1>Detections folder not found</h1>"
        
        files = []
        for filename in os.listdir(detections_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file_path = os.path.join(detections_dir, filename)
                stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        # Generate HTML
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Detections Folder</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .file-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
                .file-item { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .file-item img { width: 100%; height: 200px; object-fit: cover; border-radius: 4px; }
                .file-info { margin-top: 10px; }
                .file-name { font-weight: bold; margin-bottom: 5px; }
                .file-meta { color: #666; font-size: 0.9em; }
                h1 { color: #333; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚗 Speed Camera Detections</h1>
                <p>Total images: {}</p>
                <div class="file-grid">
        """.format(len(files))
        
        for file in files:
            html += f"""
                <div class="file-item">
                    <img src="/images/{file['name']}" alt="{file['name']}" loading="lazy">
                    <div class="file-info">
                        <div class="file-name">{file['name']}</div>
                        <div class="file-meta">
                            Size: {file['size'] / 1024:.1f} KB<br>
                            Modified: {file['modified'].strftime('%Y-%m-%d %H:%M:%S')}
                        </div>
                    </div>
                </div>
            """
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"<h1>Error: {e}</h1>"

@app.route('/api/stream')
def video_stream():
    """Video stream endpoint"""
    def generate_frames():
        try:
            global speed_camera
            if not speed_camera or not running:
                # Return error frame
                error_frame = create_error_frame("Speed camera not running")
                ret, buffer = cv2.imencode('.jpg', error_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                return
            
            while running and speed_camera:
                try:
                    # Get frame from speed camera's frame buffer
                    frame = speed_camera.frame_buffer.get(timeout=0.5)
                    if frame is None:
                        continue
                    
                    # Draw detection overlay on frame
                    overlay_frame = speed_camera.draw_overlay(frame.copy())
                    
                    # Resize frame for web streaming
                    height, width = overlay_frame.shape[:2]
                    if width > 800:
                        scale = 800 / width
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        overlay_frame = cv2.resize(overlay_frame, (new_width, new_height))
                    
                    # Encode frame as JPEG
                    ret, buffer = cv2.imencode('.jpg', overlay_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if not ret:
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    time.sleep(0.1)  # Limit to ~10 FPS for web
                    
                except Exception as e:
                    logging.error(f"Stream frame error: {e}")
                    continue
                
        except Exception as e:
            logging.error(f"Stream error: {e}")
    
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def create_error_frame(message):
    """Create an error frame with text"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame.fill(50)  # Dark gray background
    
    # Add error message
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.0
    color = (0, 0, 255)  # Red text
    thickness = 2
    
    # Calculate text size and position
    text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
    text_x = (frame.shape[1] - text_size[0]) // 2
    text_y = (frame.shape[0] + text_size[1]) // 2
    
    cv2.putText(frame, message, (text_x, text_y), font, font_scale, color, thickness)
    
    return frame

@app.route('/api/stream/status')
def stream_status():
    """Check if RTSP stream is available"""
    try:
        global speed_camera, running
        
        if not running or not speed_camera:
            return jsonify({'available': False, 'error': 'Speed camera not running'})
        
        rtsp_url = config_manager.get('camera_settings.rtsp_urls', [''])[0]
        if not rtsp_url:
            return jsonify({'available': False, 'error': 'No RTSP URL configured'})
        
        # Check if speed camera has active frame buffer
        try:
            frame = speed_camera.frame_buffer.get(timeout=0.1)
            available = frame is not None
        except:
            available = False
        
        return jsonify({
            'available': available, 
            'rtsp_url': rtsp_url,
            'status': 'Speed camera streaming with detection overlay'
        })
    except Exception as e:
        return jsonify({'available': False, 'error': str(e)})

@app.route('/api/models/check/<model_name>')
def check_model(model_name):
    """Check if a YOLO model is downloaded"""
    try:
        import os
        
        # Check in models directory
        model_path = os.path.join('models', model_name)
        downloaded = os.path.exists(model_path) and os.path.getsize(model_path) > 1000  # At least 1KB
        
        return jsonify({
            'model': model_name,
            'downloaded': downloaded,
            'path': model_path if downloaded else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/download/<model_name>', methods=['POST'])
def download_model(model_name):
    """Download a YOLO model"""
    try:
        import os
        import urllib.request
        import threading
        
        # Validate model name
        valid_models = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt']
        if model_name not in valid_models:
            return jsonify({'success': False, 'error': 'Invalid model name'}), 400
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
        
        model_path = os.path.join('models', model_name)
        
        # Check if already downloaded
        if os.path.exists(model_path) and os.path.getsize(model_path) > 1000:
            return jsonify({'success': True, 'message': 'Model already downloaded'})
        
        model_urls = {
            'yolov8n.pt': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt',
            'yolov8s.pt': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt',
            'yolov8m.pt': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt',
            'yolov8l.pt': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8l.pt',
            'yolov8x.pt': 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8x.pt'
        }
        
        def download_in_background():
            try:
                logging.info(f"Starting download of {model_name}")
                url = model_urls[model_name]
                
                urllib.request.urlretrieve(url, model_path)
                
                if os.path.exists(model_path) and os.path.getsize(model_path) > 1000:
                    logging.info(f"Successfully downloaded {model_name}")
                else:
                    logging.error(f"Download verification failed for {model_name}")
                    if os.path.exists(model_path):
                        os.remove(model_path)
                        
            except Exception as e:
                logging.error(f"Download failed for {model_name}: {str(e)}")
                if os.path.exists(model_path):
                    os.remove(model_path)
        
        # Start download in background
        download_thread = threading.Thread(target=download_in_background)
        download_thread.daemon = True
        download_thread.start()
        
        return jsonify({
            'success': True, 
            'message': f'Download started for {model_name}',
            'note': 'Download is running in background. Check console for progress.'
        })
        
    except Exception as e:
        logging.error(f"Model download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('detections', exist_ok=True)
    
    try:
        logging.info("Initializing Speed Camera System")
        speed_camera = SpeedCamera()
        
        def run_camera():
            global running
            try:
                logging.info("Starting speed camera processing thread")
                running = True
                speed_camera.start()
            except Exception as e:
                logging.error(f"Camera error: {str(e)}")
                running = False
        
        camera_thread = threading.Thread(target=run_camera)
        camera_thread.daemon = True
        camera_thread.start()
        
        logging.info("Speed camera auto-started successfully")
    except Exception as e:
        logging.error(f"Failed to auto-start camera: {str(e)}")
    
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    
    print("=" * 50)
    print("📡 Server running on: http://0.0.0.0:5000")
    print("🌐 Access dashboard at: http://localhost:5000")
    print("=" * 50)
    
    logging.info("Starting Flask web server on http://0.0.0.0:5000")
    
    time.sleep(0.5)
    
    app.run(host='0.0.0.0', port=5000, debug=False) 