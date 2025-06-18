// Settings functionality

// Load configuration from server
async function loadConfig() {
    try {
        const data = await apiCall('/api/config');
        
        // Load camera settings
        document.getElementById('rtsp-url').value = data.camera_settings?.rtsp_urls?.[0] || '';
        document.getElementById('fps').value = data.camera_settings?.fps || 25;
        
        // Load detection settings
        document.getElementById('yolo-model').value = data.detection_settings?.yolo_model || 'yolov8x.pt';
        document.getElementById('confidence').value = data.detection_settings?.confidence_threshold || 0.5;
        document.getElementById('confidence-value').textContent = data.detection_settings?.confidence_threshold || 0.5;
        document.getElementById('use-gpu').value = (data.detection_settings?.use_gpu !== undefined) ? data.detection_settings.use_gpu.toString() : 'true';
        document.getElementById('min-area').value = data.detection_settings?.min_area || 800;
        document.getElementById('blur-size').value = data.detection_settings?.blur_size || 10;
        
        // Load speed settings
        document.getElementById('speed-limit').value = data.speed_settings?.speed_limit_kmh || 50;
        document.getElementById('speed-mph').value = (data.speed_settings?.speed_mph !== undefined) ? data.speed_settings.speed_mph.toString() : 'false';
        document.getElementById('min-speed-over').value = data.speed_settings?.min_speed_over || 10;
        document.getElementById('max-speed-over').value = data.speed_settings?.max_speed_over || 150;
        document.getElementById('min-time-diff').value = data.speed_settings?.min_time_diff || 0.5;
        document.getElementById('max-time-diff').value = data.speed_settings?.max_time_diff || 5.0;
        document.getElementById('min-track-length').value = data.speed_settings?.min_track_length || 100;
        document.getElementById('track-counter').value = data.speed_settings?.track_counter || 4;
        
        // Load detection zones
        document.getElementById('l2r-enabled').value = (data.detection_zones?.l2r_enabled !== undefined) ? data.detection_zones.l2r_enabled.toString() : 'true';
        document.getElementById('r2l-enabled').value = (data.detection_zones?.r2l_enabled !== undefined) ? data.detection_zones.r2l_enabled.toString() : 'true';
        document.getElementById('l2r-line-x').value = data.detection_zones?.l2r_line_x || 600;
        document.getElementById('r2l-line-x').value = data.detection_zones?.r2l_line_x || 1150;
        document.getElementById('detection-area-top').value = data.detection_zones?.detection_area_top || 300;
        document.getElementById('detection-area-bottom').value = data.detection_zones?.detection_area_bottom || 590;
        document.getElementById('detection-area-left').value = data.detection_zones?.detection_area_left || 100;
        document.getElementById('detection-area-right').value = data.detection_zones?.detection_area_right || 1820;
        
        // Load calibration settings
        document.getElementById('cal-obj-mm-l2r').value = data.calibration_settings?.cal_obj_mm_l2r || 4127;
        document.getElementById('cal-obj-px-l2r').value = data.calibration_settings?.cal_obj_px_l2r || 700;
        document.getElementById('cal-obj-mm-r2l').value = data.calibration_settings?.cal_obj_mm_r2l || 4127;
        document.getElementById('cal-obj-px-r2l').value = data.calibration_settings?.cal_obj_px_r2l || 700;
        
        // Load output settings
        document.getElementById('save-images').value = (data.output_settings?.save_images !== undefined) ? data.output_settings.save_images.toString() : 'true';
        document.getElementById('image-quality').value = data.output_settings?.image_quality || 95;
        document.getElementById('image-quality-value').textContent = data.output_settings?.image_quality || 95;
        
        // Load vehicle settings
        document.getElementById('ignore-yolo-validation').value = (data.vehicle_settings?.ignore_yolo_validation !== undefined) ? data.vehicle_settings.ignore_yolo_validation.toString() : 'false';
        
        // Load vehicle classes list
        const vehicleClasses = data.vehicle_settings?.vehicle_classes || [];
        document.getElementById('vehicle-classes').value = vehicleClasses.join('\n');
        
        // Update slider displays
        setupSliderUpdates();
        
        // Check model download status
        checkModelDownload();
        
    } catch (error) {
        console.error('Error loading config:', error);
        showNotification('Error loading configuration', 'error');
    }
}

// Update configuration on server
async function updateConfig() {
    try {
        const config = {
            camera_settings: {
                rtsp_urls: [document.getElementById('rtsp-url').value],
                fps: parseInt(document.getElementById('fps').value)
            },
            detection_settings: {
                yolo_model: document.getElementById('yolo-model').value,
                confidence_threshold: parseFloat(document.getElementById('confidence').value),
                use_gpu: document.getElementById('use-gpu').value === 'true',
                min_area: parseInt(document.getElementById('min-area').value),
                blur_size: parseInt(document.getElementById('blur-size').value)
            },
            speed_settings: {
                speed_limit_kmh: parseInt(document.getElementById('speed-limit').value),
                speed_mph: document.getElementById('speed-mph').value === 'true',
                min_speed_over: parseInt(document.getElementById('min-speed-over').value),
                max_speed_over: parseInt(document.getElementById('max-speed-over').value),
                min_time_diff: parseFloat(document.getElementById('min-time-diff').value),
                max_time_diff: parseFloat(document.getElementById('max-time-diff').value),
                min_track_length: parseInt(document.getElementById('min-track-length').value),
                track_counter: parseInt(document.getElementById('track-counter').value)
            },
            detection_zones: {
                l2r_enabled: document.getElementById('l2r-enabled').value === 'true',
                r2l_enabled: document.getElementById('r2l-enabled').value === 'true',
                l2r_line_x: parseInt(document.getElementById('l2r-line-x').value),
                r2l_line_x: parseInt(document.getElementById('r2l-line-x').value),
                detection_area_top: parseInt(document.getElementById('detection-area-top').value),
                detection_area_bottom: parseInt(document.getElementById('detection-area-bottom').value),
                detection_area_left: parseInt(document.getElementById('detection-area-left').value),
                detection_area_right: parseInt(document.getElementById('detection-area-right').value)
            },
            calibration_settings: {
                cal_obj_mm_l2r: parseInt(document.getElementById('cal-obj-mm-l2r').value),
                cal_obj_px_l2r: parseInt(document.getElementById('cal-obj-px-l2r').value),
                cal_obj_mm_r2l: parseInt(document.getElementById('cal-obj-mm-r2l').value),
                cal_obj_px_r2l: parseInt(document.getElementById('cal-obj-px-r2l').value)
            },
            output_settings: {
                save_images: document.getElementById('save-images').value === 'true',
                image_quality: parseInt(document.getElementById('image-quality').value)
            },
            vehicle_settings: {
                ignore_yolo_validation: document.getElementById('ignore-yolo-validation').value === 'true',
                vehicle_classes: document.getElementById('vehicle-classes').value.split('\n').map(v => v.trim()).filter(v => v.length > 0)
            }
        };

        const data = await apiCall('/api/config', 'POST', config);
        
        if (data.status === 'success') {
            showNotification('All settings updated and saved successfully!', 'success');
        } else {
            showNotification('Error: ' + data.message, 'error');
            console.error('Config update error:', data.message);
        }
    } catch (error) {
        showNotification('Network error: ' + error.message, 'error');
        console.error('Network error updating config:', error);
    }
}

// Setup slider value updates
function setupSliderUpdates() {
    // Confidence slider
    const confidenceSlider = document.getElementById('confidence');
    const confidenceValue = document.getElementById('confidence-value');
    if (confidenceSlider && confidenceValue) {
        confidenceSlider.addEventListener('input', function() {
            confidenceValue.textContent = this.value;
        });
    }
    
    // Image quality slider
    const qualitySlider = document.getElementById('image-quality');
    const qualityValue = document.getElementById('image-quality-value');
    if (qualitySlider && qualityValue) {
        qualitySlider.addEventListener('input', function() {
            qualityValue.textContent = this.value;
        });
    }
}

// Model download functionality
async function checkModelDownload() {
    const modelSelect = document.getElementById('yolo-model');
    const modelStatus = document.getElementById('model-status');
    const downloadBtn = document.getElementById('download-model-btn');
    
    if (!modelSelect || !modelStatus || !downloadBtn) return;
    
    const selectedModel = modelSelect.value;
    
    try {
        const response = await apiCall(`/api/models/check/${selectedModel}`);
        
        if (response.downloaded) {
            modelStatus.textContent = '✅ Downloaded';
            modelStatus.style.color = '#10b981';
            downloadBtn.style.display = 'none';
        } else {
            modelStatus.textContent = '❌ Not Downloaded';
            modelStatus.style.color = '#ef4444';
            downloadBtn.style.display = 'inline-block';
        }
    } catch (error) {
        modelStatus.textContent = '⚠️ Check Failed';
        modelStatus.style.color = '#f59e0b';
        console.error('Model check error:', error);
    }
}

async function downloadModel() {
    const modelSelect = document.getElementById('yolo-model');
    const downloadBtn = document.getElementById('download-model-btn');
    const modelStatus = document.getElementById('model-status');
    
    if (!modelSelect || !downloadBtn || !modelStatus) return;
    
    const selectedModel = modelSelect.value;
    
    downloadBtn.disabled = true;
    downloadBtn.textContent = '📥 Downloading...';
    modelStatus.textContent = '📥 Downloading...';
    modelStatus.style.color = '#3b82f6';
    
    try {
        const response = await apiCall(`/api/models/download/${selectedModel}`, 'POST');
        
        if (response.success) {
            showNotification(`Model ${selectedModel} download started!`, 'success');
            // Check status after a short delay
            setTimeout(() => checkModelDownload(), 2000);
        } else {
            showNotification(`Failed to download model: ${response.error}`, 'error');
            downloadBtn.disabled = false;
            downloadBtn.textContent = '📥 Download';
        }
    } catch (error) {
        showNotification(`Download error: ${error.message}`, 'error');
        downloadBtn.disabled = false;
        downloadBtn.textContent = '📥 Download';
        console.error('Model download error:', error);
    }
}

async function saveConfig() {
    try {
        const config = collectFormData();
        const data = await apiCall('/api/config', 'POST', config);
        
        if (data.status === 'success') {
            showNotification('Configuration saved successfully!', 'success');
        } else {
            console.error('Config update error:', data.message);
            showNotification('Error: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Network error updating config:', error);
        showNotification('Network error: ' + error.message, 'error');
    }
} 