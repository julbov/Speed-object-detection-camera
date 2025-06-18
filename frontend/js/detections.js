// Detections functionality

let allViolations = [];
let selectedDetections = new Set();

// Load config and initialize filters
async function loadConfigAndInitFilters() {
    try {
        if (!configData) {
            configData = await loadConfig();
        }
        createObjectTypeFilter();
        refreshDetections();
    } catch (error) {
        console.error('Error loading config:', error);
        // Continue without filters if config fails
        refreshDetections();
    }
}

// Create object type filter dropdown from config
function createObjectTypeFilter() {
    if (!configData || !configData.vehicle_settings || !configData.vehicle_settings.vehicle_classes) {
        return;
    }
    
    const vehicleClasses = configData.vehicle_settings.vehicle_classes;
    const ignoreYoloValidation = configData.vehicle_settings.ignore_yolo_validation || false;
    
    const objectTypeSelect = document.getElementById('filter-object-type');
    if (!objectTypeSelect) return;
    
    // Clear existing options except "All Types"
    objectTypeSelect.innerHTML = '<option value="">All Types</option>';
    
    // Add vehicle classes from config
    vehicleClasses.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type.charAt(0).toUpperCase() + type.slice(1);
        objectTypeSelect.appendChild(option);
    });
    
    // Add "unknown" option if ignore_yolo_validation is enabled
    if (ignoreYoloValidation) {
        const unknownOption = document.createElement('option');
        unknownOption.value = 'unknown';
        unknownOption.textContent = 'Unknown';
        objectTypeSelect.appendChild(unknownOption);
    }
}

// Refresh detections from server
async function refreshDetections() {
    try {
        const violationsOnly = document.getElementById('violations-only').checked;
        const url = `/api/detections${violationsOnly ? '?violations_only=true' : ''}`;
        
        const detections = await apiCall(url);
        allViolations = detections;
        selectedDetections.clear();
        updateSelectionUI();
        displayDetections(detections);
    } catch (error) {
        console.error('Error loading detections:', error);
        showNotification('Error loading detections', 'error');
    }
}

// Toggle violations filter
function toggleViolationsFilter() {
    refreshDetections();
}

// Selection functions
function selectAll() {
    const checkboxes = document.querySelectorAll('.detection-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = true;
        selectedDetections.add(cb.value);
    });
    updateSelectionUI();
}

function deselectAll() {
    const checkboxes = document.querySelectorAll('.detection-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
    selectedDetections.clear();
    updateSelectionUI();
}

function toggleSelection(imageFile, checkbox) {
    if (checkbox.checked) {
        selectedDetections.add(imageFile);
    } else {
        selectedDetections.delete(imageFile);
    }
    updateSelectionUI();
}

function updateSelectionUI() {
    const count = selectedDetections.size;
    const countSpan = document.getElementById('selection-count');
    const deleteBtn = document.getElementById('delete-selected-btn');
    
    if (countSpan) {
        countSpan.textContent = `${count} selected`;
    }
    
    if (deleteBtn) {
        deleteBtn.disabled = count === 0;
    }
}

async function deleteSelected() {
    if (selectedDetections.size === 0) {
        showNotification('No detections selected', 'warning');
        return;
    }
    
    const count = selectedDetections.size;
    if (!confirm(`⚠️ Are you sure you want to delete ${count} selected detection${count > 1 ? 's' : ''}?\n\nThis will permanently delete the image files and cannot be undone.`)) {
        return;
    }
    
    try {
        let successCount = 0;
        let errorCount = 0;
        
        for (const imageFile of selectedDetections) {
            try {
                const response = await fetch(`/api/files/delete/${imageFile}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    successCount++;
                } else {
                    errorCount++;
                }
            } catch (error) {
                errorCount++;
                console.error(`Error deleting ${imageFile}:`, error);
            }
        }
        
        if (successCount > 0) {
            showNotification(`Successfully deleted ${successCount} detection${successCount > 1 ? 's' : ''}`, 'success');
        }
        
        if (errorCount > 0) {
            showNotification(`Failed to delete ${errorCount} detection${errorCount > 1 ? 's' : ''}`, 'error');
        }
        
        // Refresh the detections list
        selectedDetections.clear();
        refreshDetections();
        
    } catch (error) {
        console.error('Error during bulk delete:', error);
        showNotification('Error during bulk delete operation', 'error');
    }
}

// Apply filters to detections
function applyFilters() {
    const objectType = document.getElementById('filter-object-type')?.value || '';
    const direction = document.getElementById('filter-direction')?.value || '';
    const speedMin = parseFloat(document.getElementById('filter-speed-min')?.value) || null;
    const speedMax = parseFloat(document.getElementById('filter-speed-max')?.value) || null;
    const dateRange = document.getElementById('filter-date-range')?.value || '';
    const violationsOnly = document.getElementById('violations-only')?.checked || false;
    
    let filteredDetections = [...allViolations];
    
    // Apply object type filter
    if (objectType) {
        filteredDetections = filteredDetections.filter(d => 
            (d.object_type || '').toLowerCase().includes(objectType.toLowerCase())
        );
    }
    
    // Apply direction filter
    if (direction) {
        filteredDetections = filteredDetections.filter(d => d.direction === direction);
    }
    
    // Apply speed range filter
    if (speedMin !== null || speedMax !== null) {
        filteredDetections = filteredDetections.filter(d => {
            const speed = d.speed_kmh || 0;
            if (speedMin !== null && speed < speedMin) return false;
            if (speedMax !== null && speed > speedMax) return false;
            return true;
        });
    }
    
    // Apply date range filter
    if (dateRange) {
        const now = new Date();
        let startDate;
        
        switch(dateRange) {
            case 'today':
                startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                break;
            case 'yesterday':
                startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
                const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                filteredDetections = filteredDetections.filter(d => {
                    const detectionDate = new Date(d.timestamp);
                    return detectionDate >= startDate && detectionDate < endDate;
                });
                break;
            case 'week':
                startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                break;
            case 'month':
                startDate = new Date(now.getFullYear(), now.getMonth(), 1);
                break;
        }
        
        if (dateRange !== 'yesterday' && startDate) {
            filteredDetections = filteredDetections.filter(d => 
                new Date(d.timestamp) >= startDate
            );
        }
    }
    
    // Apply violations only filter
    if (violationsOnly) {
        filteredDetections = filteredDetections.filter(d => d.is_violation);
    }
    
    displayDetections(filteredDetections);
}

// Display detections in the grid
function displayDetections(detections) {
    const grid = document.getElementById('violations-grid');
    if (!grid) return;
    
    if (detections.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: #9ca3af;">No detections found</p>';
        return;
    }
    
    grid.innerHTML = detections.map(v => 
        `<div class="violation-card" style="display: flex; flex-direction: column; height: auto; position: relative;">
            ${v.has_image ? `
                <div style="position: absolute; top: 8px; left: 8px; z-index: 10;">
                    <input type="checkbox" class="detection-checkbox" value="${v.image_file}" 
                           onchange="toggleSelection('${v.image_file}', this)"
                           style="transform: scale(1.3); background: white; border: 2px solid #374151;">
                </div>
                <div style="position: absolute; top: 8px; right: 8px; z-index: 10;">
                    <button onclick="downloadImage('${v.image_file}')" 
                            style="background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 4px; padding: 5px 8px; cursor: pointer; font-size: 12px;"
                            title="Download Image">📥</button>
                </div>
                <img src="/images/${v.image_file}" 
                      style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px; cursor: pointer; margin-bottom: 10px;" 
                      onclick="showImage('/images/${v.image_file}', '${getImageTitle(v)}')"
                      alt="${getImageTitle(v)}">` :
                `<div style="width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; color: #9ca3af; border: 2px dashed #374151; border-radius: 8px; margin-bottom: 10px;">No Image</div>`
            }
            <div class="violation-info" style="flex: 1;">
                <div class="violation-speed" style="font-size: 1.5em; font-weight: bold; color: ${v.is_violation ? '#ef4444' : '#10b981'};">
                    ${v.speed_kmh?.toFixed(1) || 0} km/h
                    ${v.is_violation ? ' 🚨' : ' ✅'}
                </div>
                ${v.is_violation ? 
                    `<div style="color: #ef4444; font-size: 0.9em; font-weight: 500; margin: 2px 0;">⚠️ VIOLATION (Limit: ${v.speed_limit} km/h)</div>` : 
                    `<div style="color: #10b981; font-size: 0.9em; font-weight: 500; margin: 2px 0;">✅ Within Limit (${v.speed_limit} km/h)</div>`
                }
                <div class="violation-time" style="color: #9ca3af; margin: 5px 0;">${new Date(v.timestamp).toLocaleString()}</div>
                <div style="color: #60a5fa; margin: 5px 0; font-weight: 500;">
                    🚗 ${v.object_type || 'Vehicle'} | ${v.direction === 'L2R' ? '➡️' : '⬅️'} ${v.direction || 'Unknown'} | 🎨 ${v.object_color || 'Unknown'}
                </div>
                ${v.confidence && v.confidence > 0 ? 
                    `<div style="color: #10b981; font-size: 1.0em; font-weight: 600; margin: 5px 0;">🎯 Confidence: ${(v.confidence * 100).toFixed(1)}%</div>` : 
                    '<div style="color: #6b7280; font-size: 0.9em;">🎯 Confidence: N/A</div>'
                }
                ${v.image_file ? `<div style="color: #9ca3af; font-size: 0.8em; margin-top: 5px;">📁 ${v.image_file}</div>` : ''}
            </div>
        </div>`
    ).join('');
    
    // Update selection UI after rendering
    updateSelectionUI();
}

// Get image title for modal
function getImageTitle(detection) {
    return `${detection.object_type || 'Vehicle'} - ${detection.speed_kmh?.toFixed(1) || 0} km/h - ${detection.object_color || 'Unknown'} - ${detection.direction || 'Unknown'}`;
}

// Export detections as CSV
async function exportCSV() {
    try {
        const violationsOnly = document.getElementById('violations-only').checked;
        const url = `/api/detections?format=csv${violationsOnly ? '&violations_only=true' : ''}`;
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const csvData = await response.text();
        const blob = new Blob([csvData], { type: 'text/csv' });
        const url2 = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url2;
        a.download = `${violationsOnly ? 'violations' : 'detections'}_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url2);
        
        showNotification('CSV exported successfully', 'success');
    } catch (error) {
        console.error('Error exporting CSV:', error);
        showNotification('Error exporting CSV', 'error');
    }
}

// Download individual image
async function downloadImage(filename) {
    try {
        const response = await fetch(`/images/${filename}`);
        if (!response.ok) throw new Error('Download failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification(`Downloaded ${filename}`, 'success');
    } catch (error) {
        console.error('Download error:', error);
        showNotification(`Failed to download ${filename}`, 'error');
    }
}

// View all images in a gallery
async function viewAllImages() {
    try {
        // Fetch image data with file sizes from API
        const response = await fetch('/api/images');
        if (!response.ok) {
            throw new Error('Failed to fetch image data');
        }
        
        const imageData = await response.json();
        
        if (imageData.length === 0) {
            showNotification('No images found', 'info');
            return;
        }
        
        // Helper function to format file size
        function formatFileSize(bytes) {
            if (bytes < 1024) return `${bytes} B`;
            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        }
        
        // Create a simple gallery modal
        const modal = document.getElementById('imageModal');
        const modalContent = modal.querySelector('.modal-content');
        
        modalContent.innerHTML = `
            <span class="close" onclick="closeModal()">&times;</span>
            <h3>Detection Images Gallery (${imageData.length} images)</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 15px; margin-top: 20px;">
                ${imageData.map(img => {
                    // Find matching detection data for additional info
                    const detection = allViolations.find(v => v.image_file === img.filename);
                    const imageTitle = detection ? getImageTitle(detection) : img.filename;
                    
                    return `
                        <div style="text-align: center; background: #1f2937; border-radius: 8px; padding: 10px;">
                            <img src="${img.path}" 
                                 style="width: 100%; height: 150px; object-fit: cover; border-radius: 4px; cursor: pointer;" 
                                 onclick="showImage('${img.path}', '${imageTitle}')"
                                 alt="${imageTitle}">
                            <div style="font-size: 0.8em; color: #9ca3af; margin-top: 8px; line-height: 1.3;">
                                ${detection ? `${detection.speed_kmh?.toFixed(1)} km/h - ${detection.object_type}` : 'Detection Image'}<br>
                                <span style="color: #60a5fa; font-weight: 500;">📁 ${formatFileSize(img.size)}</span><br>
                                <span style="color: #6b7280; font-size: 0.7em;">${new Date(img.modified).toLocaleDateString()}</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        
        modal.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading images:', error);
        showNotification('Failed to load images', 'error');
    }
}

// Initialize detections page
function initDetections() {
    loadConfigAndInitFilters();
}

// Cleanup old files function
async function cleanupOldFiles() {
    if (!confirm(`This will delete files older than 30 days. Continue?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/files/cleanup', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showNotification(`Cleaned up ${data.deleted_count} old files, freed ${data.size_freed_mb} MB`, 'success');
            refreshDetections(); // Reload detections list
        } else {
            showNotification(`Cleanup failed: ${data.message}`, 'error');
        }
    } catch (error) {
        console.error('Cleanup error:', error);
        showNotification('Cleanup failed', 'error');
    }
} 