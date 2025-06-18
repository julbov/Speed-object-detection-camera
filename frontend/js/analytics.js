// Analytics variables
let analyticsCharts = {};
let analyticsData = null;

function refreshGraphs() {
    const timeFilter = document.getElementById('time-filter').value;
    
    showNotification('Loading analytics...', 'info');
    
    const url = `/api/analytics?time_filter=${timeFilter}`;
    
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            analyticsData = data;
            updateCharts();
            updateStatsTable();
            showNotification(`Analytics refreshed (${timeFilter})`, 'success');
        })
        .catch(error => {
            console.error('Error loading analytics:', error);
            showNotification('Failed to load analytics: ' + error.message, 'error');
        });
}

function updateCharts() {
    if (!analyticsData) return;
    
    // Destroy existing charts
    Object.values(analyticsCharts).forEach(chart => {
        if (chart) chart.destroy();
    });
    analyticsCharts = {};
    
    // Speed over time chart with dynamic time granularity
    const speedTimeCtx = document.getElementById('speedTimeChart').getContext('2d');
    
    // Determine data points and time format based on time filter
    const timeFilter = document.getElementById('time-filter').value;
    let dataPoints = analyticsData.speed_over_time;
    let timeFormat = 'HH:mm:ss';
    let maxPoints = 50;
    
    switch(timeFilter) {
        case 'hour':
            maxPoints = 60; // Show every minute for last hour
            timeFormat = 'HH:mm';
            break;
        case '3hour':
            maxPoints = 36; // Show every 5 minutes for last 3 hours
            timeFormat = 'HH:mm';
            break;
        case 'day':
            maxPoints = 24; // Show every hour for last day
            timeFormat = 'HH:mm';
            break;
        case 'week':
            maxPoints = 14; // Show every 12 hours for last week
            timeFormat = 'MM/DD HH:mm';
            break;
        default:
            maxPoints = 20; // Show last 20 data points for all time
            timeFormat = 'MM/DD HH:mm';
    }
    
    // Take appropriate slice of data
    const chartData = dataPoints.slice(-maxPoints);
    
    analyticsCharts.speedTime = new Chart(speedTimeCtx, {
        type: 'line',
        data: {
            labels: chartData.map(d => {
                const date = new Date(d.timestamp);
                switch(timeFormat) {
                    case 'HH:mm':
                        return date.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', hour12: false});
                    case 'MM/DD HH:mm':
                        return date.toLocaleString('en-US', {month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false});
                    default:
                        return date.toLocaleTimeString();
                }
            }),
            datasets: [{
                label: 'Average Speed (km/h)',
                data: chartData.map(d => d.speed),
                borderColor: '#60a5fa',
                backgroundColor: 'rgba(96, 165, 250, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            const dataIndex = context[0].dataIndex;
                            const timestamp = chartData[dataIndex].timestamp;
                            return new Date(timestamp).toLocaleString();
                        },
                        label: function(context) {
                            const dataIndex = context.dataIndex;
                            const item = chartData[dataIndex];
                            const labels = [
                                `Average Speed: ${context.parsed.y.toFixed(1)} km/h`,
                                `Type: ${item.type}`,
                                `Direction: ${item.direction}`
                            ];
                            
                            // Add count if available (for averaged data)
                            if (item.count !== undefined) {
                                labels.push(`Detections: ${item.count}`);
                            }
                            
                            return labels;
                        }
                    }
                }
            },
            scales: {
                y: { 
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Average Speed (km/h)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    }
                }
            }
        }
    });
    
    // Speed distribution chart
    const speedDistCtx = document.getElementById('speedDistChart').getContext('2d');
    analyticsCharts.speedDist = new Chart(speedDistCtx, {
        type: 'bar',
        data: {
            labels: Object.keys(analyticsData.speed_distribution),
            datasets: [{
                label: 'Count',
                data: Object.values(analyticsData.speed_distribution),
                backgroundColor: '#10b981',
                borderColor: '#059669',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
    
    // Vehicle types chart
    const vehicleTypeCtx = document.getElementById('vehicleTypeChart').getContext('2d');
    analyticsCharts.vehicleType = new Chart(vehicleTypeCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(analyticsData.vehicle_types),
            datasets: [{
                data: Object.values(analyticsData.vehicle_types),
                backgroundColor: [
                    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#c9d1d9', font: { size: 11 } }
                }
            }
        }
    });
    
    // Vehicle colors chart
    const vehicleColorCtx = document.getElementById('vehicleColorChart').getContext('2d');
    const colorLabels = Object.keys(analyticsData.vehicle_colors);
    const colorValues = Object.values(analyticsData.vehicle_colors);
    
    // Map color names to actual colors
    const colorMap = {
        'red': '#ef4444',
        'blue': '#3b82f6',
        'green': '#10b981',
        'yellow': '#f59e0b',
        'black': '#374151',
        'white': '#f3f4f6',
        'gray': '#6b7280',
        'silver': '#9ca3af',
        'brown': '#92400e',
        'orange': '#ea580c',
        'purple': '#8b5cf6',
        'pink': '#ec4899'
    };
    
    const backgroundColors = colorLabels.map(color => 
        colorMap[color.toLowerCase()] || '#60a5fa'
    );
    
    analyticsCharts.vehicleColor = new Chart(vehicleColorCtx, {
        type: 'doughnut',
        data: {
            labels: colorLabels,
            datasets: [{
                data: colorValues,
                backgroundColor: backgroundColors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#c9d1d9', font: { size: 11 } }
                }
            }
        }
    });
    
    // Direction analysis chart
    const directionCtx = document.getElementById('directionChart').getContext('2d');
    analyticsCharts.direction = new Chart(directionCtx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(analyticsData.directions),
            datasets: [{
                data: Object.values(analyticsData.directions),
                backgroundColor: ['#60a5fa', '#f59e0b']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#c9d1d9', font: { size: 11 } }
                }
            }
        }
    });
    
    // Hourly activity chart with dynamic labels
    const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
    const currentTimeFilter = document.getElementById('time-filter').value;
    
    // Format labels based on time filter and data
    let chartLabels = Object.keys(analyticsData.hourly_activity);
    let chartTitle = 'Hourly Activity';
    
    if (currentTimeFilter === 'hour') {
        chartTitle = 'Activity (5-minute intervals)';
        // Labels are already in HH:MM format for hour filter
    } else if (currentTimeFilter === '3hour') {
        chartTitle = 'Activity (15-minute intervals)';
        // Labels are already in HH:MM format for 3hour filter
    } else {
        chartTitle = 'Hourly Activity';
        // Add :00 suffix for hour-only labels
        chartLabels = chartLabels.map(h => {
            // Check if it's already in HH:MM format
            if (h.includes(':')) {
                return h;
            } else {
                return h + ':00';
            }
        });
    }
    
    analyticsCharts.hourly = new Chart(hourlyCtx, {
        type: 'bar',
        data: {
            labels: chartLabels,
            datasets: [{
                label: 'Detections',
                data: Object.values(analyticsData.hourly_activity),
                backgroundColor: '#8b5cf6',
                borderColor: '#7c3aed',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: chartTitle,
                    color: '#c9d1d9'
                }
            },
            scales: {
                y: { 
                    beginAtZero: true,
                    ticks: { color: '#c9d1d9' }
                },
                x: {
                    ticks: { 
                        color: '#c9d1d9',
                        maxRotation: 45
                    }
                }
            }
        }
    });
}

function updateStatsTable() {
    if (!analyticsData || !analyticsData.stats) return;
    
    const stats = analyticsData.stats;
    const directions = analyticsData.directions || {};
    const container = document.getElementById('stats-summary');
    
    // Get direction counts safely
    const l2rCount = directions['L2R'] || directions['l2r'] || directions['left_to_right'] || 0;
    const r2lCount = directions['R2L'] || directions['r2l'] || directions['right_to_left'] || 0;
    
    container.innerHTML = `
        <div class="status-card">
            <div class="status-value">${stats.total_detections || 0}</div>
            <div class="status-label">Total Detections</div>
        </div>
        <div class="status-card">
            <div class="status-value">${(stats.avg_speed || 0).toFixed(1)} km/h</div>
            <div class="status-label">Average Speed</div>
        </div>
        <div class="status-card">
            <div class="status-value">${(stats.max_speed || 0).toFixed(1)} km/h</div>
            <div class="status-label">Max Speed</div>
        </div>
        <div class="status-card">
            <div class="status-value">${stats.violations || 0}</div>
            <div class="status-label">Speed Violations</div>
        </div>
        <div class="status-card">
            <div class="status-value">${l2rCount}</div>
            <div class="status-label">Left to Right</div>
        </div>
        <div class="status-card">
            <div class="status-value">${r2lCount}</div>
            <div class="status-label">Right to Left</div>
        </div>
    `;
}

function refreshDataTable() {
    const maxRows = document.getElementById('table-rows').value;
    const typeFilter = document.getElementById('type-filter') ? document.getElementById('type-filter').value : 'all';
    
    let url = `/api/detections?limit=${maxRows}`;
    if (typeFilter !== 'all') {
        url += `&type=${typeFilter}`;
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('data-table-body');
            tbody.innerHTML = '';
            
            data.forEach(detection => {
                const row = document.createElement('tr');
                row.style.borderBottom = '1px solid #4b5563';
                
                const timestamp = new Date(detection.timestamp).toLocaleString();
                const imageLink = detection.image_file ? 
                    `<button onclick="showImage('/images/${detection.image_file}', '${getImageTitle(detection)}')" style="background: none; border: none; color: #60a5fa; cursor: pointer; text-decoration: underline;">View</button>` : 
                    'N/A';
                
                row.innerHTML = `
                    <td style="border: 1px solid #4b5563; padding: 8px;">${timestamp}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.object_type}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.object_color}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.direction}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.speed_kmh}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.speed_mph}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${detection.confidence}</td>
                    <td style="border: 1px solid #4b5563; padding: 8px;">${imageLink}</td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading data table:', error);
            showNotification('Failed to load data table', 'error');
        });
}

function exportAnalytics() {
    if (!analyticsData) {
        showNotification('No analytics data to export', 'error');
        return;
    }
    
    const dataStr = JSON.stringify(analyticsData, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(dataBlob);
    link.download = `speed_camera_analytics_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    showNotification('Analytics exported successfully', 'success');
}

function exportTableData() {
    const maxRows = document.getElementById('table-rows').value;
    
    fetch(`/api/detections?limit=${maxRows}&format=csv`)
        .then(response => response.blob())
        .then(blob => {
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `detections_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();
            showNotification('Data exported successfully', 'success');
        })
        .catch(error => {
            console.error('Error exporting data:', error);
            showNotification('Failed to export data', 'error');
        });
}

// Helper functions for image popup
function getImageTitle(detection) {
    const timestamp = new Date(detection.timestamp).toLocaleString();
    return `${detection.object_type} - ${detection.speed_kmh} km/h - ${timestamp}`;
}

function showImage(imageSrc, title) {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        cursor: pointer;
    `;
    
    // Create image container
    const container = document.createElement('div');
    container.style.cssText = `
        max-width: 90%;
        max-height: 90%;
        text-align: center;
    `;
    
    // Create image
    const img = document.createElement('img');
    img.src = imageSrc;
    img.style.cssText = `
        max-width: 100%;
        max-height: 80vh;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    `;
    
    // Create title
    const titleDiv = document.createElement('div');
    titleDiv.textContent = title;
    titleDiv.style.cssText = `
        color: white;
        margin-top: 10px;
        font-size: 16px;
        background: rgba(0, 0, 0, 0.7);
        padding: 10px;
        border-radius: 4px;
    `;
    
    container.appendChild(img);
    container.appendChild(titleDiv);
    overlay.appendChild(container);
    
    // Close on click
    overlay.addEventListener('click', () => {
        document.body.removeChild(overlay);
    });
    
    document.body.appendChild(overlay);
}

// Load config data and initialize filters
async function loadConfigAndInitFilters() {
    try {
        if (!configData) {
            configData = await loadConfig();
        }
        createTypeFilter();
        refreshGraphs();
        refreshDataTable();
    } catch (error) {
        console.error('Error loading config:', error);
        showNotification('Failed to load config, continuing without filters', 'warning');
        refreshGraphs();
        refreshDataTable();
    }
}

// Create type filter dropdown from config
function createTypeFilter() {
    if (!configData || !configData.vehicle_settings || !configData.vehicle_settings.vehicle_classes) {
        return;
    }
    
    const vehicleClasses = configData.vehicle_settings.vehicle_classes;
    const ignoreYoloValidation = configData.vehicle_settings.ignore_yolo_validation || false;
    
    // Find the table controls area
    const tableControls = document.querySelector('#data-table-container').previousElementSibling;
    
    // Create type filter
    const typeFilterSpan = document.createElement('span');
    typeFilterSpan.style.marginLeft = '15px';
    typeFilterSpan.innerHTML = `
        Type: 
        <select id="type-filter" onchange="refreshDataTable()" style="padding: 3px; background: #374151; color: white; border: 1px solid #4b5563; border-radius: 4px;">
            <option value="all">All Types</option>
            ${vehicleClasses.map(type => `<option value="${type}">${type}</option>`).join('')}
            ${ignoreYoloValidation ? '<option value="unknown">unknown</option>' : ''}
        </select>
    `;
    
    tableControls.appendChild(typeFilterSpan);
}

// Initialize analytics when page loads
async function initAnalytics() {
    // Load Chart.js if not already loaded
    if (typeof Chart === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        script.onload = () => {
            loadConfigAndInitFilters();
        };
        document.head.appendChild(script);
    } else {
        await loadConfigAndInitFilters();
    }
} 