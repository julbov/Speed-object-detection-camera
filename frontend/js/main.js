// Main JavaScript for Speed Camera Dashboard

// Global variables
let currentTab = 'dashboard';
let streamActive = false;
let configData = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadComponents();
    showTab('dashboard');
    updateStatus();
    
    // Auto-refresh status every 3 seconds
    setInterval(updateStatus, 3000);
    
    // Auto-refresh dashboard content every 5 seconds
    setInterval(() => {
        if (currentTab === 'dashboard') {
            // Refresh latest detection
            if (typeof updateLatestDetection === 'function') {
                updateLatestDetection();
            }
            // Console auto-refresh is handled in dashboard.js
        }
    }, 5000);
    
    // Auto-refresh content based on current tab
    setInterval(() => {
        switch(currentTab) {
            case 'detections':
                if (typeof refreshDetections === 'function') {
                    refreshDetections();
                }
                break;

            case 'analytics':
                if (typeof refreshGraphs === 'function') {
                    refreshGraphs();
                }
                break;
        }
    }, 30000);
});

async function loadComponents() {
    try {
        const dashboardResponse = await fetch('components/dashboard.html');
        const dashboardHTML = await dashboardResponse.text();
        document.getElementById('dashboard-content').innerHTML = dashboardHTML;
        
        const settingsResponse = await fetch('components/settings.html');
        const settingsHTML = await settingsResponse.text();
        document.getElementById('settings-content').innerHTML = settingsHTML;
        
        const detectionsResponse = await fetch('components/detections.html');
        const detectionsHTML = await detectionsResponse.text();
        document.getElementById('detections-content').innerHTML = detectionsHTML;
        
        const analyticsResponse = await fetch('components/analytics.html');
        const analyticsHTML = await analyticsResponse.text();
        document.getElementById('analytics-content').innerHTML = analyticsHTML;
        
        loadConfig();
        
    } catch (error) {
        console.error('Error loading components:', error);
        showNotification('Error loading interface components', 'error');
    }
}

function showTab(tabName) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Find and activate the clicked tab
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.textContent.toLowerCase().includes(tabName.toLowerCase())) {
            item.classList.add('active');
        }
    });
    
    // Hide all tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });
    
    // Show selected tab content
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
        selectedTab.style.display = 'block';
    }
    
    currentTab = tabName;
    
    // Load tab-specific data
    switch(tabName) {
        case 'dashboard':
            updateStatus();
            if (typeof updateLatestDetection === 'function') {
                updateLatestDetection();
            }
            break;
        case 'settings':
            loadConfig();
            break;
        case 'detections':
            if (typeof initDetections === 'function') {
                initDetections();
            }
            if (typeof refreshDetections === 'function') {
                refreshDetections();
            }
            break;
        case 'analytics':
            if (typeof initAnalytics === 'function') {
                initAnalytics();
            }
            break;

    }
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 4000);
}

// Modal functionality
function showImage(src, title) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modal-image');
    const modalTitle = document.getElementById('modal-title');
    
    modal.style.display = 'block';
    modalImg.src = src;
    modalTitle.textContent = title;
}

function closeModal() {
    document.getElementById('imageModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('imageModal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
}

// API helper functions
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(endpoint, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        throw error;
    }
}

// Update system status
async function updateStatus() {
    try {
        const data = await apiCall('/api/status');
        
        // Update header status indicators
        const headerIndicator = document.querySelector('#camera-status .indicator');
        const headerStatusText = document.getElementById('status-text');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (headerIndicator && headerStatusText) {
            if (data.running && data.camera_connected) {
                headerIndicator.className = 'indicator online';
                headerStatusText.textContent = 'Online';
                if (startBtn) startBtn.disabled = true;
                if (stopBtn) stopBtn.disabled = false;
            } else if (data.running) {
                headerIndicator.className = 'indicator warning';
                headerStatusText.textContent = 'Starting...';
                if (startBtn) startBtn.disabled = true;
                if (stopBtn) stopBtn.disabled = false;
            } else {
                headerIndicator.className = 'indicator offline';
                headerStatusText.textContent = 'Offline';
                if (startBtn) startBtn.disabled = false;
                if (stopBtn) stopBtn.disabled = true;
            }
        }

        // Update stats safely
        const updateElement = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };

        updateElement('violations-count', data.violations_count || 0);
        updateElement('frames-processed', data.total_frames || 0);
        updateElement('memory-usage', (data.memory_usage || 0).toFixed(1) + '%');
        updateElement('images-size', data.images_size || '0 MB');
        
        // Format uptime nicely
        const uptimeSeconds = data.uptime || 0;
        let uptimeText = '';
        if (uptimeSeconds < 60) {
            uptimeText = `${uptimeSeconds}s`;
        } else if (uptimeSeconds < 3600) {
            const minutes = Math.floor(uptimeSeconds / 60);
            const seconds = uptimeSeconds % 60;
            uptimeText = `${minutes}m ${seconds}s`;
        } else if (uptimeSeconds < 86400) {
            const hours = Math.floor(uptimeSeconds / 3600);
            const minutes = Math.floor((uptimeSeconds % 3600) / 60);
            uptimeText = `${hours}h ${minutes}m`;
        } else {
            const days = Math.floor(uptimeSeconds / 86400);
            const hours = Math.floor((uptimeSeconds % 86400) / 3600);
            uptimeText = `${days}d ${hours}h`;
        }
        updateElement('uptime', uptimeText);
        
        // Update video stream only if stream is active
        const videoStream = document.getElementById('video-stream');
        if (videoStream && data.running && data.camera_connected && streamActive) {
            // Force refresh video stream by adding timestamp
            const streamUrl = `/api/stream?t=${Date.now()}`;
            if (videoStream.src !== streamUrl) {
                videoStream.src = streamUrl;
            }
        }
        
    } catch (error) {
        console.error('Error updating status:', error);
        const headerStatusText = document.getElementById('status-text');
        const headerIndicator = document.querySelector('#camera-status .indicator');
        if (headerStatusText && headerIndicator) {
            headerIndicator.className = 'indicator offline';
            headerStatusText.textContent = 'Connection Error';
        }
    }
}

// System control functions
async function startCamera() {
    try {
        const data = await apiCall('/api/start', 'POST');
        if (data.status === 'success') {
            showNotification('Speed camera started!', 'success');
            setTimeout(updateStatus, 1000);
            setTimeout(updateStatus, 3000);
        } else {
            showNotification('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showNotification('Network error: ' + error.message, 'error');
    }
}

async function stopCamera() {
    if (!confirm('⚠️ Are you sure you want to stop the speed camera system?\n\nThis will stop all detection and monitoring.')) {
        return;
    }
    
    try {
        const data = await apiCall('/api/stop', 'POST');
        if (data.status === 'success') {
            showNotification('Speed camera stopped!', 'success');
            setTimeout(updateStatus, 1000);
            setTimeout(updateStatus, 3000);
        } else {
            showNotification('Error: ' + data.message, 'error');
        }
    } catch (error) {
        showNotification('Network error: ' + error.message, 'error');
    }
}

async function refreshStatus() {
    try {
        const data = await apiCall('/api/status');
        
        // Update status values
        updateElementText('violations-count', data.violations_count || 0);
        updateElementText('frames-processed', data.frames_processed || 0);
        updateElementText('memory-usage', `${data.memory_usage?.toFixed(1) || 0}%`);
        updateElementText('images-size', data.images_size || '0 MB');
        
        // Format uptime nicely
        const uptimeSeconds = data.uptime || 0;
        let uptimeText = '';
        if (uptimeSeconds < 60) {
            uptimeText = `${uptimeSeconds}s`;
        } else if (uptimeSeconds < 3600) {
            const minutes = Math.floor(uptimeSeconds / 60);
            const seconds = uptimeSeconds % 60;
            uptimeText = `${minutes}m ${seconds}s`;
        } else if (uptimeSeconds < 86400) {
            const hours = Math.floor(uptimeSeconds / 3600);
            const minutes = Math.floor((uptimeSeconds % 3600) / 60);
            uptimeText = `${hours}h ${minutes}m`;
        } else {
            const days = Math.floor(uptimeSeconds / 86400);
            const hours = Math.floor((uptimeSeconds % 86400) / 3600);
            uptimeText = `${days}d ${hours}h`;
        }
        updateElementText('uptime', uptimeText);
        
        // GPU status
        if (data.gpu_enabled) {
            updateElementText('gpu-usage', `${data.gpu_usage?.toFixed(1) || 0}%`);
        } else {
            updateElementText('gpu-usage', 'Disabled');
        }
        
        // Update system status indicator
        const statusIndicator = document.getElementById('system-status');
        if (statusIndicator) {
            if (data.running) {
                statusIndicator.textContent = '🟢 Running';
                statusIndicator.style.color = '#10b981';
            } else {
                statusIndicator.textContent = '🔴 Stopped';
                statusIndicator.style.color = '#ef4444';
            }
        }
        
    } catch (error) {
        console.error('Error refreshing status:', error);
        // Set default values on error
        updateElementText('violations-count', '0');
        updateElementText('frames-processed', '0');
        updateElementText('memory-usage', '0%');
        updateElementText('images-size', '0 MB');
        updateElementText('uptime', '0s');
        updateElementText('gpu-usage', 'Error');
    }
}

// Helper function to update element text safely
function updateElementText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

// Global config loading function
async function loadConfig() {
    try {
        configData = await apiCall('/api/config');
        return configData;
    } catch (error) {
        console.error('Error loading global config:', error);
        configData = null;
        return null;
    }
} 