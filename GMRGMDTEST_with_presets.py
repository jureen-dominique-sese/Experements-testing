import webview
import numpy as np
from datetime import datetime
import json
import os

# [Previous Python code until HTML template]

html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Transmission Line Calculator</title>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>
:root {
  --primary: #0078d4;
  --surface: #ffffff;
  --background: #f5f5f5;
  --on-surface: #242424;
  --on-surface-medium: #666666;
  --divider: #e0e0e0;
  --shadow: rgba(0, 0, 0, 0.1);
}

/* [Previous CSS styles] */

/* Bundle Dialog Styles */
.bundle-dialog {
  position: fixed;
  z-index: 1000;
  background: var(--surface);
  border-radius: 8px;
  box-shadow: 0 4px 12px var(--shadow);
  min-width: 300px;
  animation: fadeIn 0.2s ease-out;
}

.dialog-content {
  padding: 1.5rem;
}

.dialog-content h3 {
  margin: 0 0 1rem;
  color: var(--on-surface);
  font-size: 1.2rem;
}

.dialog-buttons {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* [Rest of previous CSS] */
</style>
</head>
<body>
<!-- [Previous HTML content until script tag] -->

<script>
// Bundle preset configurations
const bundlePresets = {
  'three': {
    name: '3-Conductor Bundle',
    points: [
      [0, 0],
      [0, 0],
      [0, 0]
    ]
  },
  'four': {
    name: '4-Conductor Bundle',
    points: [
      [0, 0],
      [0, 0],
      [0, 0],
      [0, 0]
    ]
  }
};

function calculateBundlePoints(centerX, centerY, bundleType, spacing) {
  const points = [];
  const radius = spacing / 2;
  
  if (bundleType === 'three') {
    // Equilateral triangle configuration
    const angleStep = (2 * Math.PI) / 3;
    for (let i = 0; i < 3; i++) {
      const angle = i * angleStep;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      points.push([parseFloat(x.toFixed(3)), parseFloat(y.toFixed(3))]);
    }
  } else if (bundleType === 'four') {
    // Square configuration
    const positions = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    for (const [dx, dy] of positions) {
      const x = centerX + (dx * radius / Math.sqrt(2));
      const y = centerY + (dy * radius / Math.sqrt(2));
      points.push([parseFloat(x.toFixed(3)), parseFloat(y.toFixed(3))]);
    }
  }
  
  return points;
}

function showBundleDialog(e, x, y) {
  // Remove any existing dialogs
  document.querySelectorAll('.bundle-dialog').forEach(d => d.remove());
  
  const dialog = document.createElement('div');
  dialog.className = 'bundle-dialog';
  dialog.innerHTML = `
    <div class="dialog-content">
      <h3>Add Bundle Preset</h3>
      <div class="input-group">
        <label>Bundle Type</label>
        <select id="bundleType" class="form-control">
          <option value="three">3-Conductor Bundle</option>
          <option value="four">4-Conductor Bundle</option>
        </select>
      </div>
      <div class="input-group">
        <label>Spacing between conductors (m)</label>
        <input type="number" id="bundleSpacing" class="form-control" value="0.4" step="0.1" min="0.1">
      </div>
      <div class="dialog-buttons">
        <button class="btn btn-outline" onclick="this.closest('.bundle-dialog').remove()">Cancel</button>
        <button class="btn btn-primary" onclick="applyBundlePreset(${x}, ${y})">Apply</button>
      </div>
    </div>
  `;
  
  // Position the dialog near the click, but ensure it stays in viewport
  const rect = document.body.getBoundingClientRect();
  let left = e.clientX;
  let top = e.clientY;
  
  // Add to document to get dimensions
  dialog.style.visibility = 'hidden';
  document.body.appendChild(dialog);
  const dialogRect = dialog.getBoundingClientRect();
  
  // Adjust position if needed
  if (left + dialogRect.width > rect.right) {
    left = rect.right - dialogRect.width - 10;
  }
  if (top + dialogRect.height > rect.bottom) {
    top = rect.bottom - dialogRect.height - 10;
  }
  
  dialog.style.left = left + 'px';
  dialog.style.top = top + 'px';
  dialog.style.visibility = 'visible';
  
  // Close dialog when clicking outside
  function closeOnClickOutside(event) {
    if (!dialog.contains(event.target)) {
      dialog.remove();
      document.removeEventListener('mousedown', closeOnClickOutside);
    }
  }
  document.addEventListener('mousedown', closeOnClickOutside);
}

async function applyBundlePreset(centerX, centerY) {
  const dialog = document.querySelector('.bundle-dialog');
  const bundleType = document.getElementById('bundleType').value;
  const spacing = parseFloat(document.getElementById('bundleSpacing').value);
  
  const points = calculateBundlePoints(centerX, centerY, bundleType, spacing);
  
  for (const [x, y] of points) {
    await pywebview.api.add_point(x.toString(), y.toString(), activeBundle);
    bundles[activeBundle].push([x, y]);
  }
  
  dialog.remove();
  redraw();
  await updateResults();
}

// Event Listeners
canvas.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  
  if (isPanning) return;
  
  const rect = canvas.getBoundingClientRect();
  const mx = ((e.clientX - rect.left) * canvas.width / rect.width - panOffset.x) / zoomLevel;
  const my = ((e.clientY - rect.top) * canvas.height / rect.height - panOffset.y) / zoomLevel;
  
  const x = parseFloat(((mx - origin.x) / scaleX).toFixed(3));
  const y = parseFloat(((origin.y - my) / scaleY).toFixed(3));
  
  showBundleDialog(e, x, y);
});

canvas.addEventListener('click', async (e) => {
  if (isPanning) return;
  
  const rect = canvas.getBoundingClientRect();
  const mx = ((e.clientX - rect.left) * canvas.width / rect.width - panOffset.x) / zoomLevel;
  const my = ((e.clientY - rect.top) * canvas.height / rect.height - panOffset.y) / zoomLevel;
  
  const x = ((mx - origin.x) / scaleX).toFixed(3);
  const y = ((origin.y - my) / scaleY).toFixed(3);
  
  await pywebview.api.add_point(x, y, activeBundle);
  bundles[activeBundle].push([parseFloat(x), parseFloat(y)]);
  
  redraw();
  await updateResults();
});

// [Rest of previous JavaScript code]
</script>
</body>
</html>
"""

# [Rest of Python code]