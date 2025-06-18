// Dashboard functionality

// streamActive is now global in main.js
let allConsoleLogs = [];
let consoleAutoRefresh = null;

// Video stream controls
function startVideoStream() {
    const videoStream = document.getElementById('video-stream');
    const streamError = document.getElementById('stream-error');
    const startBtn = document.getElementById('start-stream-btn');
    const stopBtn = document.getElementById('stop-stream-btn');
    
    if (videoStream && streamError) {
        streamActive = true;
        videoStream.src = `/api/stream?t=${Date.now()}`;
        videoStream.style.display = 'block';
        streamError.style.display = 'none';
        
        if (startBtn) startBtn.disabled = true;
        if (stopBtn) stopBtn.disabled = false;
        
        showNotification('Video stream started', 'success');
    }
}

function stopVideoStream() {
    const videoStream = document.getElementById('video-stream');
    const streamError = document.getElementById('stream-error');
    const startBtn = document.getElementById('start-stream-btn');
    const stopBtn = document.getElementById('stop-stream-btn');
    
    if (videoStream && streamError) {
        streamActive = false;
        videoStream.src = '';
        videoStream.style.display = 'none';
        streamError.style.display = 'flex';
        
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
        
        showNotification('Video stream stopped', 'info');
    }
}

// Console functionality
async function refreshConsole() {
    try {
        const response = await apiCall('/api/console?limit=200');
        
        // Handle both old and new API formats
        if (Array.isArray(response)) {
            // Old format - direct array
            allConsoleLogs = response;
        } else if (response.logs) {
            // New format - object with metadata
            allConsoleLogs = response.logs || [];
            
            // Update debug status
            const debugEnabled = response.debug_enabled || false;
            const debugCheckbox = document.getElementById('filter-debug');
            if (debugCheckbox && debugEnabled) {
                debugCheckbox.checked = true;
            }
            
            // Show debug info if available
            if (response.total_count !== undefined) {
        
            }
        } else {
            allConsoleLogs = [];
        }
        
        displayConsole();
    } catch (error) {
        console.error('Error loading console:', error);
        const consoleOutput = document.getElementById('console-output');
        if (consoleOutput) {
            consoleOutput.innerHTML = '<div style="color: #ef4444; text-align: center; padding: 20px;">Error loading console logs</div>';
        }
    }
}

function clearConsole() {
    if (confirm('Clear all console logs?')) {
        allConsoleLogs = [];
        displayConsole();
        showNotification('Console cleared', 'info');
    }
}

function filterConsole() {
    displayConsole();
}

function displayConsole() {
    const consoleOutput = document.getElementById('console-output');
    if (!consoleOutput) return;
    
    // Get filter states
    const showInfo = document.getElementById('filter-info')?.checked ?? true;
    const showWarning = document.getElementById('filter-warning')?.checked ?? true;
    const showError = document.getElementById('filter-error')?.checked ?? true;
    const showDebug = document.getElementById('filter-debug')?.checked ?? false;
    const showSpeedCamera = document.getElementById('filter-speed-camera')?.checked ?? true;
    
    // Filter logs
    const filteredLogs = allConsoleLogs.filter(log => {
        const level = log.level?.toLowerCase() || 'info';
        const module = log.module?.toLowerCase() || '';
        const message = log.message?.toLowerCase() || '';
        
        // Level filtering
        if (level === 'info' && !showInfo) return false;
        if (level === 'warning' && !showWarning) return false;
        if (level === 'error' && !showError) return false;
        if (level === 'debug' && !showDebug) return false;
        
        // Module/content filtering
        if (module === 'speed_camera' || message.includes('track') || message.includes('frame') || message.includes('gpu')) {
            return showSpeedCamera;
        }
        
        return true;
    });
    
    if (filteredLogs.length === 0) {
        consoleOutput.innerHTML = '<div style="color: #9ca3af; text-align: center; padding: 20px;">No console logs match current filters</div>';
        return;
    }
    
    // Display logs - consistent format
    const logHtml = filteredLogs.slice(-100).map(log => {
        const timestamp = new Date(log.timestamp).toLocaleTimeString();
        const level = log.level || 'INFO';
        const module = log.module || 'system';
        const message = log.message || '';
        
        let levelColor = '#9ca3af';
        let levelIcon = 'ℹ️';
        
        switch(level.toLowerCase()) {
            case 'info':
                levelColor = '#10b981';
                levelIcon = 'ℹ️';
                break;
            case 'warning':
                levelColor = '#f59e0b';
                levelIcon = '⚠️';
                break;
            case 'error':
                levelColor = '#ef4444';
                levelIcon = '❌';
                break;
            case 'debug':
                levelColor = '#8b5cf6';
                levelIcon = '🐛';
                break;
        }
        
        // Single consistent format
        return `
            <div style="margin-bottom: 2px; padding: 2px 4px; border-left: 2px solid ${levelColor}; display: flex; align-items: center; gap: 6px;">
                <span style="color: #9ca3af; font-size: 0.7em; min-width: 60px;">${timestamp.substring(0, 8)}</span>
                <span style="color: ${levelColor}; font-size: 0.8em;">${levelIcon}</span>
                <span style="color: #60a5fa; font-size: 0.7em; min-width: 50px;">[${module.substring(0, 8)}]</span>
                <span style="color: #e5e7eb; font-size: 0.8em; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${message}</span>
            </div>
        `;
    }).join('');
    
    consoleOutput.innerHTML = logHtml;
    
    // Auto-scroll to bottom if enabled
    if (document.getElementById('auto-scroll')?.checked) {
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
}



// Start console auto-refresh when dashboard is active
function startConsoleAutoRefresh() {
    if (consoleAutoRefresh) {
        clearInterval(consoleAutoRefresh);
    }
    
    // Initial load
    refreshConsole();
    
    // Auto-refresh every 1 second
    consoleAutoRefresh = setInterval(() => {
        if (currentTab === 'dashboard') {
            refreshConsole();
        }
    }, 1000);
}

function stopConsoleAutoRefresh() {
    if (consoleAutoRefresh) {
        clearInterval(consoleAutoRefresh);
        consoleAutoRefresh = null;
    }
}

// Update latest detection display
async function updateLatestDetection() {
    try {
        const detections = await apiCall('/api/detections?limit=1');
        const latestDiv = document.getElementById('latest-detection');
        
        if (!latestDiv) return;
        
        if (detections.length === 0) {
            latestDiv.innerHTML = '<div style="text-align: center; color: #9ca3af;">No recent detections</div>';
            return;
        }
        
        const latest = detections[0];
        const timeAgo = getTimeAgo(new Date(latest.timestamp));
        
        latestDiv.innerHTML = `
            <div style="text-align: center; width: 100%;">
                ${latest.has_image ? 
                    `<img src="/images/${latest.image_file}" 
                          style="width: 100%; max-width: 300px; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 15px; cursor: pointer;" 
                          onclick="showImage('/images/${latest.image_file}', '${getImageTitle(latest)}')"
                          alt="Latest detection">` :
                    `<div style="width: 100%; max-width: 300px; height: 200px; display: flex; align-items: center; justify-content: center; background: #374151; border-radius: 8px; margin: 0 auto 15px; color: #9ca3af;">📷 No Image</div>`
                }
                <div style="font-size: 1.4em; font-weight: bold; color: ${latest.is_violation ? '#ef4444' : '#10b981'}; margin-bottom: 10px;">
                    ${latest.speed_kmh?.toFixed(1) || 0} km/h ${latest.is_violation ? '🚨' : '✅'}
                </div>
                <div style="color: #60a5fa; margin-bottom: 8px; font-size: 1.1em;">
                    🚗 ${latest.object_type || 'Vehicle'} | ${latest.direction === 'L2R' ? '➡️' : '⬅️'} ${latest.direction || 'Unknown'}
                </div>
                <div style="color: #9ca3af; font-size: 0.95em; margin-bottom: 5px;">
                    🎨 ${latest.object_color || 'Unknown'}
                </div>
                <div style="color: #9ca3af; font-size: 0.9em;">
                    ${timeAgo}
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Error updating latest detection:', error);
        const latestDiv = document.getElementById('latest-detection');
        if (latestDiv) {
            latestDiv.innerHTML = '<div style="text-align: center; color: #ef4444;">Error loading latest detection</div>';
        }
    }
}

// Get time ago string
function getTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSecs < 60) return `${diffSecs}s ago`;
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
}

// Get image title for modal (reuse from detections.js)
function getImageTitle(detection) {
    return `${detection.object_type || 'Vehicle'} - ${detection.speed_kmh?.toFixed(1) || 0} km/h - ${detection.object_color || 'Unknown'} - ${detection.direction || 'Unknown'}`;
}

// Auto-update latest detection every 10 seconds
setInterval(() => {
    if (currentTab === 'dashboard') {
        updateLatestDetection();
    }
}, 10000);

// Update latest detection when dashboard tab is shown
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for components to load
    setTimeout(() => {
        if (currentTab === 'dashboard') {
            updateLatestDetection();
            startConsoleAutoRefresh();
        }
    }, 2000);
});

// Handle tab switching for console
document.addEventListener('tabChanged', function(event) {
    if (event.detail === 'dashboard') {
        startConsoleAutoRefresh();
    } else {
        stopConsoleAutoRefresh();
    }
}); 