import numpy as np
import webview
from itertools import combinations, product

# ---------- Unit Conversion ----------
UNIT_CONVERSIONS = {
    "m": 1.0,
    "ft": 0.3048,
    "inch": 0.0254,
    "cm": 0.01,
    "mm": 0.001
}

# Material resistivity at 20°C (Ω·m)
MATERIALS = {
    "Copper": 1.68e-8,
    "Aluminum": 2.82e-8,
    "Steel": 1.43e-7,
    "ACSR": 3.2e-8
}

# ---------- Math Utilities ----------
def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

def geometric_mean(values):
    return np.prod(values) ** (1 / len(values))

def compute_gmr(bundle_points, r_self):
    n = len(bundle_points)
    if n == 1:
        return r_self
    distances = [distance(p1, p2) for p1, p2 in combinations(bundle_points, 2)]
    all_terms = [r_self] * n + distances
    gmr = np.prod(all_terms) ** (1 / n)
    return gmr

def compute_gmd(bundle1, bundle2):
    distances = [distance(p1, p2) for p1, p2 in product(bundle1, bundle2)]
    return geometric_mean(distances)

# ---------- App Logic ----------
class GMDGMRApp:
    def __init__(self):
        self.bundles = {"A": [], "B": [], "C": []}
        self.r_self = {"A": 0.01, "B": 0.01, "C": 0.01}
        self.unit = "m"
        self.scale_x = 40
        self.scale_y = 40
        
        # Line parameters
        self.material = "Copper"
        self.length = 100.0  # km
        self.conductor_radius = 0.01  # m
        self.freq = 60.0  # Hz

    def set_unit(self, u):
        if u in UNIT_CONVERSIONS:
            self.unit = u
        return f"Units set to {u}"

    def set_scale(self, sx, sy):
        self.scale_x = float(sx)
        self.scale_y = float(sy)
        return "Scales updated"

    def set_gmr(self, bundle, val):
        self.r_self[bundle] = float(val) * UNIT_CONVERSIONS[self.unit]
        return f"Set GMR for {bundle} = {val} {self.unit}"

    def set_line_params(self, material, length, radius, freq):
        self.material = material
        self.length = float(length)
        self.conductor_radius = float(radius)
        self.freq = float(freq)
        return "Parameters updated"

    def add_point(self, x, y, bundle):
        x_m = float(x) * UNIT_CONVERSIONS[self.unit]
        y_m = float(y) * UNIT_CONVERSIONS[self.unit]
        self.bundles[bundle].append((x_m, y_m))
        return "ok"

    def clear_bundle(self, bundle):
        self.bundles[bundle] = []
        return f"Cleared {bundle}"

    def clear_all(self):
        self.bundles = {"A": [], "B": [], "C": []}
        return "All cleared"

    def compute_results(self):
        results = {"gmr": [], "gmd": [], "params": {}}
        gmr_values = {}
        
        # GMR calculations
        for label, points in self.bundles.items():
            if points:
                gmr_values[label] = compute_gmr(points, self.r_self[label])
                results["gmr"].append({
                    "label": label,
                    "value": gmr_values[label],
                    "count": len(points)
                })
        
        # GMD calculations
        gmd_values = {}
        for (a, b) in combinations(self.bundles.keys(), 2):
            if self.bundles[a] and self.bundles[b]:
                gmd = compute_gmd(self.bundles[a], self.bundles[b])
                gmd_values[f"{a}-{b}"] = gmd
                results["gmd"].append({
                    "pair": f"{a}-{b}",
                    "value": gmd
                })
        
        # Parameter calculations (3-phase assumed)
        if len(gmr_values) >= 1:
            # Resistance (Ω/km)
            rho = MATERIALS.get(self.material, 1.68e-8)
            area = np.pi * (self.conductor_radius ** 2)
            n_conductors = max(len(self.bundles[b]) for b in self.bundles if self.bundles[b])
            R_per_km = (rho * 1000) / (area * n_conductors) if n_conductors > 0 else 0
            R_total = R_per_km * self.length
            
            # Inductance (H/km and H total)
            if len(gmr_values) >= 2:
                avg_gmd = np.mean(list(gmd_values.values())) if gmd_values else 1.0
                avg_gmr = np.mean(list(gmr_values.values()))
                L_per_km = 2e-7 * np.log(avg_gmd / avg_gmr) * 1000  # H/km
                L_total = L_per_km * self.length
            else:
                L_per_km = 0
                L_total = 0
            
            # Capacitance (F/km and F total)
            if len(gmr_values) >= 2:
                r_equiv = self.conductor_radius * (n_conductors ** 0.5) if n_conductors > 0 else self.conductor_radius
                C_per_km = (2 * np.pi * 8.854e-12 * 1000) / np.log(avg_gmd / r_equiv)  # F/km
                C_total = C_per_km * self.length
            else:
                C_per_km = 0
                C_total = 0
            
            # Reactances
            omega = 2 * np.pi * self.freq
            XL = omega * L_total if L_total > 0 else 0
            XC = (1 / (omega * C_total)) if C_total > 0 else 0
            
            results["params"] = {
                "R_per_km": R_per_km,
                "R_total": R_total,
                "L_per_km": L_per_km * 1000,  # mH/km
                "L_total": L_total * 1000,  # mH
                "C_per_km": C_per_km * 1e9,  # nF/km
                "C_total": C_total * 1e6,  # µF
                "XL": XL,
                "XC": XC
            }
        
        return results

# ---------- Modern Windows-Style UI ----------
html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Transmission Line Calculator</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: #f3f3f3;
  --panel: #ffffff;
  --panel-dark: #fafafa;
  --fg: #1f1f1f;
  --fg-secondary: #605e5c;
  --accent: #0078d4;
  --accent-hover: #106ebe;
  --accent-pressed: #005a9e;
  --border: #e1dfdd;
  --shadow-sm: 0 1.6px 3.6px rgba(0,0,0,.13), 0 0.3px 0.9px rgba(0,0,0,.11);
  --shadow-md: 0 3.2px 7.2px rgba(0,0,0,.13), 0 0.6px 1.8px rgba(0,0,0,.11);
  --shadow-lg: 0 6.4px 14.4px rgba(0,0,0,.13), 0 1.2px 3.6px rgba(0,0,0,.11);
  --radius: 4px;
  --radius-lg: 8px;
}

* { 
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--fg);
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

/* Title Bar */
.titlebar {
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: var(--shadow-sm);
  z-index: 100;
}

.titlebar-icon {
  width: 20px;
  height: 20px;
  color: var(--accent);
}

.titlebar-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--fg);
  letter-spacing: -0.01em;
}

/* Main Layout */
.app-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Sidebar */
.sidebar {
  width: 320px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-section {
  padding: 20px;
  border-bottom: 1px solid var(--border);
}

.sidebar-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
  margin-bottom: 6px;
}

.form-control {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 13px;
  background: var(--panel);
  color: var(--fg);
  transition: all 0.15s ease;
}

.form-control:hover {
  border-color: #bdbdbd;
}

.form-control:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.form-row {
  display: flex;
  gap: 10px;
}

.form-row .form-group {
  flex: 1;
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius);
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.btn-primary {
  background: var(--accent);
  color: white;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-primary:active {
  background: var(--accent-pressed);
}

.btn-secondary {
  background: var(--panel-dark);
  color: var(--fg);
  border: 1px solid var(--border);
}

.btn-secondary:hover {
  background: #f5f5f5;
}

.btn-danger {
  background: #d13438;
  color: white;
}

.btn-danger:hover {
  background: #a72828;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-block {
  width: 100%;
}

/* Bundle Selector */
.bundle-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.bundle-btn {
  flex: 1;
  padding: 10px;
  border: 2px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--fg);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.bundle-btn:hover {
  border-color: #bdbdbd;
}

.bundle-btn.active {
  border-color: var(--accent);
  background: rgba(0, 120, 212, 0.05);
  color: var(--accent);
}

.bundle-btn[data-bundle="A"].active {
  border-color: #d83b01;
  color: #d83b01;
  background: rgba(216, 59, 1, 0.05);
}

.bundle-btn[data-bundle="B"].active {
  border-color: #0078d4;
  color: #0078d4;
  background: rgba(0, 120, 212, 0.05);
}

.bundle-btn[data-bundle="C"].active {
  border-color: #107c10;
  color: #107c10;
  background: rgba(16, 124, 16, 0.05);
}

/* Canvas Area */
.canvas-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--panel-dark);
}

.canvas-toolbar {
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--panel-dark);
  border-radius: var(--radius);
  border: 1px solid var(--border);
}

.toolbar-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--fg-secondary);
}

.toolbar-input {
  width: 60px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 12px;
  background: var(--panel);
}

.canvas-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  position: relative;
}

canvas {
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  cursor: crosshair;
}

.coord-display {
  position: absolute;
  bottom: 32px;
  left: 32px;
  background: rgba(0, 0, 0, 0.85);
  color: white;
  padding: 8px 14px;
  border-radius: var(--radius);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
  box-shadow: var(--shadow-md);
}

.canvas-legend {
  position: absolute;
  top: 32px;
  right: 32px;
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 14px;
  box-shadow: var(--shadow-md);
}

.legend-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--fg-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.legend-item:last-child {
  margin-bottom: 0;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

/* Right Panel */
.results-panel {
  width: 380px;
  background: var(--panel);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.results-header {
  padding: 16px 20px;
  background: var(--panel-dark);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 13px;
  color: var(--fg-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.results-content {
  padding: 20px;
  flex: 1;
}

.result-card {
  background: var(--panel-dark);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 16px;
}

.result-card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.result-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.result-label {
  font-size: 13px;
  color: var(--fg-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.result-value {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--fg);
}

.bundle-badge {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--fg-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  opacity: 0.3;
}

.empty-text {
  font-size: 14px;
  line-height: 1.5;
}

/* Parameter Result Highlights */
.param-highlight {
  background: linear-gradient(135deg, rgba(0,120,212,0.05) 0%, rgba(16,124,16,0.05) 100%);
  padding: 12px;
  border-radius: var(--radius);
  border-left: 3px solid var(--accent);
}

.param-highlight .result-value {
  color: var(--accent);
  font-size: 14px;
}
</style>
</head>
<body>

<!-- Title Bar -->
<div class="titlebar">
  <svg class="titlebar-icon" fill="currentColor" viewBox="0 0 20 20">
    <path d="M13 7H7v6h6V7z"/>
    <path fill-rule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clip-rule="evenodd"/>
  </svg>
  <span class="titlebar-title">Transmission Line Parameter Calculator</span>
</div>

<!-- Main App Container -->
<div class="app-container">
  
  <!-- Left Sidebar -->
  <div class="sidebar">
    
    <!-- Bundle Selection -->
    <div class="sidebar-section">
      <div class="section-title">Active Bundle</div>
      <div class="bundle-selector">
        <button class="bundle-btn active" data-bundle="A" onclick="setActiveBundle('A')">A</button>
        <button class="bundle-btn" data-bundle="B" onclick="setActiveBundle('B')">B</button>
        <button class="bundle-btn" data-bundle="C" onclick="setActiveBundle('C')">C</button>
      </div>
      
      <div class="form-row" style="margin-top: 12px;">
        <button class="btn btn-danger btn-sm btn-block" onclick="clearCurrent()">Clear Bundle</button>
        <button class="btn btn-danger btn-sm btn-block" onclick="clearAll()">Clear All</button>
      </div>
    </div>
    
    <!-- Units & GMR -->
    <div class="sidebar-section">
      <div class="section-title">Geometry Settings</div>
      
      <div class="form-group">
        <label class="form-label">Distance Units</label>
        <select id="unit" class="form-control" onchange="updateUnit()">
          <option value="m">Meters (m)</option>
          <option value="ft">Feet (ft)</option>
          <option value="inch">Inches (in)</option>
          <option value="cm">Centimeters (cm)</option>
          <option value="mm">Millimeters (mm)</option>
        </select>
      </div>
      
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">GMR A</label>
          <input id="gA" type="number" step="0.001" value="0.01" class="form-control">
        </div>
        <div class="form-group">
          <label class="form-label">GMR B</label>
          <input id="gB" type="number" step="0.001" value="0.01" class="form-control">
        </div>
        <div class="form-group">
          <label class="form-label">GMR C</label>
          <input id="gC" type="number" step="0.001" value="0.01" class="form-control">
        </div>
      </div>
      
      <button class="btn btn-primary btn-sm btn-block" onclick="setGMRs()">Apply GMR Values</button>
    </div>
    
    <!-- Line Parameters -->
    <div class="sidebar-section">
      <div class="section-title">Line Parameters</div>
      
      <div class="form-group">
        <label class="form-label">Material</label>
        <select id="material" class="form-control">
          <option value="Copper">Copper</option>
          <option value="Aluminum">Aluminum</option>
          <option value="Steel">Steel</option>
          <option value="ACSR">ACSR</option>
        </select>
      </div>
      
      <div class="form-group">
        <label class="form-label">Line Length (km)</label>
        <input id="length" type="number" step="0.1" value="100" class="form-control">
      </div>
      
      <div class="form-group">
        <label class="form-label">Conductor Radius (m)</label>
        <input id="radius" type="number" step="0.001" value="0.01" class="form-control">
      </div>
      
      <div class="form-group">
        <label class="form-label">Frequency (Hz)</label>
        <input id="freq" type="number" step="0.1" value="60" class="form-control">
      </div>
      
      <button class="btn btn-primary btn-block" onclick="updateLineParams()">Calculate Parameters</button>
    </div>
    
  </div>
  
  <!-- Canvas Area -->
  <div class="canvas-area">
    
    <!-- Canvas Toolbar -->
    <div class="canvas-toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">Scale X:</span>
        <input id="scaleX" type="number" value="40" class="toolbar-input">
        <span class="toolbar-label">Y:</span>
        <input id="scaleY" type="number" value="40" class="toolbar-input">
        <button class="btn btn-secondary btn-sm" onclick="updateScale()">Apply</button>
      </div>
      
      <div style="margin-left: auto; font-size: 12px; color: var(--fg-secondary);">
        Click on canvas to place conductors • Distance visualizations appear automatically
      </div>
    </div>
    
    <!-- Canvas -->
    <div class="canvas-wrapper">
      <canvas id="plane" width="1000" height="700"></canvas>
      <div class="coord-display" id="coordDisplay">x: 0.000, y: 0.000</div>
      
      <div class="canvas-legend">
        <div class="legend-title">Bundles</div>
        <div class="legend-item">
          <div class="legend-color" style="background: #d83b01;"></div>
          <span>Bundle A</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: #0078d4;"></div>
          <span>Bundle B</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background: #107c10;"></div>
          <span>Bundle C</span>
        </div>
      </div>
    </div>
    
  </div>
  
  <!-- Results Panel -->
  <div class="results-panel">
    <div class="results-header">Calculation Results</div>
    <div class="results-content" id="results">
      <div class="empty-state">
        <svg class="empty-icon" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"/>
        </svg>
        <p class="empty-text">Click on the canvas to place conductor points and see calculations</p>
      </div>
    </div>
  </div>
  
</div>

<script>
const canvas = document.getElementById('plane');
const ctx = canvas.getContext('2d');
const colors = {A: '#d83b01', B: '#0078d4', C: '#107c10'};
let bundles = {A: [], B: [], C: []};
let activeBundle = 'A';
let scaleX = 40, scaleY = 40;
const origin = {x: 80, y: canvas.height - 80};

// ===== Snap & Preview System =====
const SNAP_RADIUS = 15;
const SNAP_COLOR = "#FFB900";
let snapPoint = null;
let allPoints = [];
let lastPlacedPoint = null;
let mousePos = {x: 0, y: 0};
let shiftKeyPressed = false;

// Track keyboard state
let inputDialog = null;

window.addEventListener('keydown', (e) => {
  if (e.key === 'Shift') shiftKeyPressed = true;
  
  // TAB to open input dialog for direct length input
  if (e.key === 'Tab' && lastPlacedPoint) {
    e.preventDefault();
    openLengthInputDialog();
  }
  
  // ESC key to clear pointer and restart
  if (e.key === 'Escape') {
    lastPlacedPoint = null;
    snapPoint = null;
    mousePos = {x: 0, y: 0};
    redraw();
    
    const display = document.getElementById('coordDisplay');
    display.textContent = 'Pointer cleared • Ready for new bundle';
    display.style.background = 'rgba(16, 124, 16, 0.9)';
    display.style.opacity = '1';
    
    setTimeout(() => {
      display.style.opacity = '0';
    }, 2000);
  }
});

window.addEventListener('keyup', (e) => {
  if (e.key === 'Shift') shiftKeyPressed = false;
});

function openLengthInputDialog() {
  if (inputDialog) return; // Prevent multiple dialogs
  
  // Create overlay
  const overlay = document.createElement('div');
  overlay.id = 'input-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  `;
  
  // Create dialog
  const dialog = document.createElement('div');
  dialog.style.cssText = `
    background: white;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    min-width: 300px;
    font-family: Inter, sans-serif;
  `;
  
  dialog.innerHTML = `
    <div style="margin-bottom: 16px;">
      <h3 style="font-size: 16px; font-weight: 600; color: #1f1f1f; margin-bottom: 8px;">Enter Line Parameters</h3>
    </div>
    
    <div style="margin-bottom: 16px;">
      <label style="display: block; font-size: 13px; font-weight: 500; color: #1f1f1f; margin-bottom: 6px;">Length</label>
      <input 
        id="length-input" 
        type="number" 
        step="0.001" 
        placeholder="Enter distance"
        style="
          width: 100%;
          padding: 8px 10px;
          border: 1px solid #e1dfdd;
          border-radius: 4px;
          font-size: 13px;
          font-family: Consolas, Monaco, monospace;
          box-sizing: border-box;
        "
      >
    </div>
    
    <div style="margin-bottom: 16px;">
      <label style="display: block; font-size: 13px; font-weight: 500; color: #1f1f1f; margin-bottom: 6px;">Angle (degrees)</label>
      <input 
        id="angle-input" 
        type="number" 
        step="0.1" 
        value="0"
        min="0"
        max="360"
        placeholder="0 to 360"
        style="
          width: 100%;
          padding: 8px 10px;
          border: 1px solid #e1dfdd;
          border-radius: 4px;
          font-size: 13px;
          font-family: Consolas, Monaco, monospace;
          box-sizing: border-box;
        "
      >
      <p style="font-size: 11px; color: #605e5c; margin: 6px 0 0 0;">0° = Right, 90° = Up, 180° = Left, 270° = Down</p>
    </div>
    
    <div style="display: flex; gap: 10px;">
      <button id="confirm-btn" style="
        flex: 1;
        padding: 8px 16px;
        background: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
      ">Place Point</button>
      <button id="cancel-btn" style="
        flex: 1;
        padding: 8px 16px;
        background: #fafafa;
        color: #1f1f1f;
        border: 1px solid #e1dfdd;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
      ">Cancel</button>
    </div>
  `;
  
  overlay.appendChild(dialog);
  document.body.appendChild(overlay);
  
  const lengthInput = document.getElementById('length-input');
  const angleInput = document.getElementById('angle-input');
  const confirmBtn = document.getElementById('confirm-btn');
  const cancelBtn = document.getElementById('cancel-btn');
  
  // Calculate angle based on current mouse position
  const dx = mousePos.x - lastPlacedPoint.x;
  const dy = lastPlacedPoint.y - mousePos.y; // Flip Y for standard angle measurement
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  const normalizedAngle = angle < 0 ? angle + 360 : angle;
  angleInput.value = normalizedAngle.toFixed(1);
  
  lengthInput.focus();
  inputDialog = overlay;
  
  // Hover effects
  confirmBtn.addEventListener('mouseover', () => {
    confirmBtn.style.background = '#106ebe';
  });
  confirmBtn.addEventListener('mouseout', () => {
    confirmBtn.style.background = '#0078d4';
  });
  
  cancelBtn.addEventListener('mouseover', () => {
    cancelBtn.style.background = '#f5f5f5';
  });
  cancelBtn.addEventListener('mouseout', () => {
    cancelBtn.style.background = '#fafafa';
  });
  
  function closeDialog() {
    if (inputDialog) {
      inputDialog.remove();
      inputDialog = null;
    }
  }
  
  function placePointWithLength() {
    const length = parseFloat(lengthInput.value);
    const angle = parseFloat(angleInput.value);
    
    if (!length || length <= 0) {
      alert('Please enter a valid positive length');
      return;
    }
    
    if (isNaN(angle) || angle < 0 || angle > 360) {
      alert('Please enter a valid angle (0-360)');
      return;
    }
    
    // Convert angle to radians (standard math convention: 0° = right)
    const radians = (angle * Math.PI) / 180;
    
    // Calculate new point using angle and length
    const newX = lastPlacedPoint.x + (length * scaleX * Math.cos(radians));
    const newY = lastPlacedPoint.y - (length * scaleY * Math.sin(radians)); // Flip Y
    
    // Convert to coordinates
    const coordX = ((newX - origin.x) / scaleX).toFixed(3);
    const coordY = ((origin.y - newY) / scaleY).toFixed(3);
    
    // Place the point
    (async () => {
      await pywebview.api.add_point(coordX, coordY, activeBundle);
      bundles[activeBundle].push([parseFloat(coordX), parseFloat(coordY)]);
      
      lastPlacedPoint = {x: newX, y: newY};
      
      animatePointPlacement(newX, newY, colors[activeBundle]);
      updateAllPoints();
      redraw();
      await updateResults();
    })();
    
    closeDialog();
  }
  
  confirmBtn.addEventListener('click', placePointWithLength);
  cancelBtn.addEventListener('click', closeDialog);
  
  // Enter key to confirm
  lengthInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      placePointWithLength();
    }
  });
  
  // Escape to cancel
  lengthInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDialog();
    }
  });
}

function updateAllPoints() {
  allPoints = [];
  for (let bundle in bundles) {
    bundles[bundle].forEach(([x, y], i) => {
      const canvasX = origin.x + x * scaleX;
      const canvasY = origin.y - y * scaleY;
      allPoints.push({
        x: canvasX,
        y: canvasY,
        bundle: bundle,
        index: i,
        coordX: x,
        coordY: y
      });
    });
  }
}

function findSnapPoint(mouseX, mouseY) {
  let nearest = null;
  let minDist = SNAP_RADIUS;
  
  for (let p of allPoints) {
    const dx = p.x - mouseX;
    const dy = p.y - mouseY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    if (dist < minDist) {
      minDist = dist;
      nearest = p;
    }
  }
  
  return nearest;
}

function getConstrainedPoint(currentX, currentY) {
  if (!shiftKeyPressed || !lastPlacedPoint) {
    return {x: currentX, y: currentY, type: 'free'};
  }
  
  const dx = currentX - lastPlacedPoint.x;
  const dy = currentY - lastPlacedPoint.y;
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);
  
  // If closer to horizontal, constrain to Y
  if (absDx > absDy) {
    return {x: currentX, y: lastPlacedPoint.y, type: 'horizontal'};
  } else {
    return {x: lastPlacedPoint.x, y: currentY, type: 'vertical'};
  }
}

function drawSnapIndicator() {
  if (!snapPoint) return;
  
  ctx.beginPath();
  ctx.arc(snapPoint.x, snapPoint.y, 12, 0, 2 * Math.PI);
  ctx.strokeStyle = SNAP_COLOR;
  ctx.lineWidth = 2.5;
  ctx.globalAlpha = 0.8;
  ctx.stroke();
  
  ctx.beginPath();
  ctx.arc(snapPoint.x, snapPoint.y, 6, 0, 2 * Math.PI);
  ctx.fillStyle = SNAP_COLOR;
  ctx.globalAlpha = 0.3;
  ctx.fill();
  
  ctx.globalAlpha = 1;
}

function drawPreviewLine() {
  if (!lastPlacedPoint) return;
  
  const constrainedPos = getConstrainedPoint(mousePos.x, mousePos.y);
  const targetX = constrainedPos.x;
  const targetY = constrainedPos.y;
  
  // Draw preview line
  ctx.beginPath();
  ctx.moveTo(lastPlacedPoint.x, lastPlacedPoint.y);
  ctx.lineTo(targetX, targetY);
  ctx.strokeStyle = colors[activeBundle];
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 5]);
  ctx.globalAlpha = 0.6;
  ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.setLineDash([]);
  
  // Calculate distance
  const dx = targetX - lastPlacedPoint.x;
  const dy = targetY - lastPlacedPoint.y;
  const canvasDistPx = Math.sqrt(dx * dx + dy * dy);
  const canvasDistUnits = canvasDistPx / scaleX;
  
  // Draw constraint indicator if shift pressed
  if (shiftKeyPressed) {
    if (constrainedPos.type === 'horizontal') {
      ctx.fillStyle = colors[activeBundle];
      ctx.font = 'bold 12px Inter, sans-serif';
      ctx.fillText('HORIZONTAL', targetX + 10, targetY - 15);
    } else {
      ctx.fillStyle = colors[activeBundle];
      ctx.font = 'bold 12px Inter, sans-serif';
      ctx.fillText('VERTICAL', targetX + 10, targetY - 15);
    }
  }
  
  // Draw distance label
  const midX = (lastPlacedPoint.x + targetX) / 2;
  const midY = (lastPlacedPoint.y + targetY) / 2;
  
  ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
  ctx.fillRect(midX - 35, midY - 25, 70, 24);
  
  ctx.fillStyle = colors[activeBundle];
  ctx.font = 'bold 12px Consolas, Monaco, monospace';
  ctx.textAlign = 'center';
  ctx.fillText(canvasDistUnits.toFixed(3), midX, midY - 8);
  ctx.textAlign = 'left';
}

// ===== Bundle Management =====
function setActiveBundle(bundle) {
  activeBundle = bundle;
  document.querySelectorAll('.bundle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.bundle === bundle);
  });
}

// ===== Drawing Functions =====
function drawGrid() {
  ctx.strokeStyle = "#f5f5f5";
  ctx.lineWidth = 1;
  
  for (let x = 0; x < canvas.width; x += scaleX) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += scaleY) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }
  
  ctx.strokeStyle = "#424242";
  ctx.lineWidth = 2;
  ctx.shadowColor = "rgba(0,0,0,0.1)";
  ctx.shadowBlur = 4;
  
  ctx.beginPath();
  ctx.moveTo(0, origin.y);
  ctx.lineTo(canvas.width, origin.y);
  ctx.stroke();
  
  ctx.beginPath();
  ctx.moveTo(origin.x, 0);
  ctx.lineTo(origin.x, canvas.height);
  ctx.stroke();
  
  ctx.shadowBlur = 0;
  
  ctx.fillStyle = "#424242";
  ctx.font = "600 12px Inter, sans-serif";
  ctx.fillText("(0, 0)", origin.x + 8, origin.y - 8);
}

function drawBundleConnections(points, color) {
  if (points.length < 2) return;
  
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = 1;
  
  // Draw actual line connections
  for (let i = 0; i < points.length - 1; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[i + 1];
    const cx1 = origin.x + x1 * scaleX;
    const cy1 = origin.y - y1 * scaleY;
    const cx2 = origin.x + x2 * scaleX;
    const cy2 = origin.y - y2 * scaleY;
    
    ctx.beginPath();
    ctx.moveTo(cx1, cy1);
    ctx.lineTo(cx2, cy2);
    ctx.stroke();
    
    // Draw segment distance
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    const mx = (cx1 + cx2) / 2;
    const my = (cy1 + cy2) / 2;
    
    ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.fillRect(mx - 30, my - 20, 60, 20);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(mx - 30, my - 20, 60, 20);
    
    ctx.fillStyle = color;
    ctx.font = 'bold 11px Consolas, Monaco, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(dist.toFixed(3), mx, my - 7);
    ctx.textAlign = 'left';
  }
  
  ctx.globalAlpha = 1;
}

function getBundleCenter(points) {
  if (points.length === 0) return null;
  
  let cx = 0, cy = 0;
  points.forEach(([x, y]) => {
    cx += x;
    cy += y;
  });
  cx /= points.length;
  cy /= points.length;
  
  return {x: cx, y: cy};
}

function drawBundleCircle(points, color) {
  if (points.length < 2) return;
  
  let cx = 0, cy = 0;
  points.forEach(([x, y]) => {
    cx += x;
    cy += y;
  });
  cx /= points.length;
  cy /= points.length;
  
  let maxR = 0;
  points.forEach(([x, y]) => {
    const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
    maxR = Math.max(maxR, dist);
  });
  
  const centerX = origin.x + cx * scaleX;
  const centerY = origin.y - cy * scaleY;
  const radius = maxR * scaleX * 1.2;
  
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 4]);
  ctx.globalAlpha = 0.3;
  
  ctx.beginPath();
  ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
  ctx.stroke();
  
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}

function drawGMDLines() {
  // Get all bundles with points
  const bundlesWithPoints = Object.keys(bundles).filter(b => bundles[b].length > 0);
  
  if (bundlesWithPoints.length < 2) return;
  
  // GMD pairs to display
  const pairs = [
    ['A', 'B'],
    ['B', 'C'],
    ['A', 'C']
  ];
  
  pairs.forEach(([b1, b2]) => {
    if (bundles[b1].length > 0 && bundles[b2].length > 0) {
      // Get bundle centers
      const c1 = getBundleCenter(bundles[b1]);
      const c2 = getBundleCenter(bundles[b2]);
      
      const x1 = origin.x + c1.x * scaleX;
      const y1 = origin.y - c1.y * scaleY;
      const x2 = origin.x + c2.x * scaleX;
      const y2 = origin.y - c2.y * scaleY;
      
      // Calculate GMD (geometric mean distance between bundles)
      const dx = c2.x - c1.x;
      const dy = c2.y - c1.y;
      const gmd = Math.sqrt(dx * dx + dy * dy);
      
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;
      
      // Draw dashed line
      ctx.strokeStyle = '#FF6B35';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([5, 5]);
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
      
      // Draw bundle center markers
      ctx.fillStyle = '#FF6B35';
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.arc(x1, y1, 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x2, y2, 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.globalAlpha = 1;
      
      // Draw GMD label box
      ctx.fillStyle = '#FFF5F0';
      ctx.fillRect(mx - 65, my - 20, 130, 28);
      
      ctx.strokeStyle = '#FF6B35';
      ctx.lineWidth = 2;
      ctx.strokeRect(mx - 65, my - 20, 130, 28);
      
      // GMD label text
      ctx.fillStyle = '#FF6B35';
      ctx.font = 'bold 13px Consolas, Monaco, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`GMD ${b1}-${b2}: ${gmd.toFixed(4)}`, mx, my + 3);
      ctx.textAlign = 'left';
    }
  });
}

function drawPoints() {
  for (let b in bundles) {
    ctx.fillStyle = colors[b];
    bundles[b].forEach(([x, y], i) => {
      const cx = origin.x + x * scaleX;
      const cy = origin.y - y * scaleY;
      
      ctx.shadowColor = "rgba(0,0,0,0.25)";
      ctx.shadowBlur = 8;
      ctx.shadowOffsetY = 2;
      
      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, 2 * Math.PI);
      ctx.fill();
      
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;
      
      ctx.fillStyle = "rgba(255,255,255,0.4)";
      ctx.beginPath();
      ctx.arc(cx - 1, cy - 1, 3, 0, 2 * Math.PI);
      ctx.fill();
      
      ctx.fillStyle = "rgba(255,255,255,0.95)";
      const label = b + (i + 1);
      ctx.font = "bold 11px Inter, sans-serif";
      const metrics = ctx.measureText(label);
      const labelWidth = metrics.width + 8;
      
      ctx.fillRect(cx + 12, cy - 16, labelWidth, 18);
      ctx.strokeStyle = colors[b];
      ctx.lineWidth = 1;
      ctx.strokeRect(cx + 12, cy - 16, labelWidth, 18);
      
      ctx.fillStyle = colors[b];
      ctx.fillText(label, cx + 16, cy - 4);
    });
  }
}

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawGrid();
  
  for (let b in bundles) {
    if (bundles[b].length > 0) {
      drawBundleCircle(bundles[b], colors[b]);
      drawBundleConnections(bundles[b], colors[b]);
    }
  }
  
  drawPoints();
  drawSnapIndicator();
  drawPreviewLine();
}

// ===== Animation =====
function animatePointPlacement(x, y, color) {
  let r = 0;
  const animate = () => {
    r += 3;
    if (r < 30) {
      redraw();
      
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.globalAlpha = 1 - (r / 30);
      ctx.stroke();
      ctx.globalAlpha = 1;
      
      requestAnimationFrame(animate);
    } else {
      redraw();
    }
  };
  animate();
}

// ===== Canvas Events =====
canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  const mx = (e.clientX - rect.left) * scaleFactorX;
  const my = (e.clientY - rect.top) * scaleFactorY;
  
  mousePos = {x: mx, y: my};
  
  snapPoint = findSnapPoint(mx, my);
  
  const x = ((mx - origin.x) / scaleX).toFixed(3);
  const y = ((origin.y - my) / scaleY).toFixed(3);
  
  const display = document.getElementById('coordDisplay');
  
  if (snapPoint) {
    display.textContent = `SNAP: ${snapPoint.bundle}${snapPoint.index + 1} (${snapPoint.coordX.toFixed(3)}, ${snapPoint.coordY.toFixed(3)})`;
    display.style.background = 'rgba(255, 185, 0, 0.9)';
  } else if (lastPlacedPoint && shiftKeyPressed) {
    display.textContent = `SHIFT: Constrained placement | x: ${x}, y: ${y}`;
    display.style.background = 'rgba(0, 120, 212, 0.9)';
  } else {
    display.textContent = `x: ${x}, y: ${y}`;
    display.style.background = 'rgba(0, 0, 0, 0.85)';
  }
  display.style.opacity = '1';
  
  redraw();
});

canvas.addEventListener('click', async (e) => {
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  const mx = (e.clientX - rect.left) * scaleFactorX;
  const my = (e.clientY - rect.top) * scaleFactorY;
  
  let finalPos;
  let x, y;
  
  if (snapPoint) {
    x = snapPoint.coordX.toFixed(3);
    y = snapPoint.coordY.toFixed(3);
    finalPos = {x: snapPoint.x, y: snapPoint.y};
  } else {
    const constrainedPos = getConstrainedPoint(mx, my);
    x = ((constrainedPos.x - origin.x) / scaleX).toFixed(3);
    y = ((origin.y - constrainedPos.y) / scaleY).toFixed(3);
    finalPos = {x: constrainedPos.x, y: constrainedPos.y};
  }
  
  await pywebview.api.add_point(x, y, activeBundle);
  bundles[activeBundle].push([parseFloat(x), parseFloat(y)]);
  
  lastPlacedPoint = finalPos;
  
  animatePointPlacement(finalPos.x, finalPos.y, colors[activeBundle]);
  updateAllPoints();
  redraw();
  await updateResults();
});

canvas.addEventListener('mouseleave', () => {
  snapPoint = null;
  document.getElementById('coordDisplay').style.opacity = '0';
});

// ESC key to clear pointer and restart
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    lastPlacedPoint = null;
    snapPoint = null;
    mousePos = {x: 0, y: 0};
    redraw();
    
    const display = document.getElementById('coordDisplay');
    display.textContent = 'Pointer cleared • Ready for new bundle';
    display.style.background = 'rgba(16, 124, 16, 0.9)';
    display.style.opacity = '1';
    
    setTimeout(() => {
      display.style.opacity = '0';
    }, 2000);
  }
});

// ===== Results Display =====
async function updateResults() {
  const results = await pywebview.api.compute_results();
  const container = document.getElementById('results');
  
  if (results.gmr.length === 0 && results.gmd.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg class="empty-icon" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"/>
        </svg>
        <p class="empty-text">Click on the canvas to place conductor points • Hold SHIFT for 90° constraints</p>
      </div>`;
    return;
  }
  
  let html = '';
  
  if (results.gmr.length > 0) {
    html += '<div class="result-card"><div class="result-card-title">Geometric Mean Radius (GMR)</div>';
    results.gmr.forEach(r => {
      html += `
        <div class="result-item">
          <span class="result-label">
            <span class="bundle-badge" style="background:${colors[r.label]}"></span>
            Bundle ${r.label} <span style="opacity:0.6; font-size:11px;">(${r.count} conductor${r.count>1?'s':''})</span>
          </span>
          <span class="result-value">${r.value.toFixed(6)} m</span>
        </div>`;
    });
    html += '</div>';
  }
  
  if (results.gmd.length > 0) {
    html += '<div class="result-card"><div class="result-card-title">Geometric Mean Distance (GMD)</div>';
    results.gmd.forEach(r => {
      html += `
        <div class="result-item">
          <span class="result-label">Distance ${r.pair}</span>
          <span class="result-value">${r.value.toFixed(6)} m</span>
        </div>`;
    });
    html += '</div>';
  }
  
  if (results.params && Object.keys(results.params).length > 0) {
    const p = results.params;
    
    html += '<div class="result-card"><div class="result-card-title">Resistance</div>';
    html += `
      <div class="result-item">
        <span class="result-label">R per km</span>
        <span class="result-value">${p.R_per_km.toFixed(6)} Ω/km</span>
      </div>
      <div class="result-item param-highlight">
        <span class="result-label">Total Resistance</span>
        <span class="result-value">${p.R_total.toFixed(4)} Ω</span>
      </div>`;
    html += '</div>';
    
    html += '<div class="result-card"><div class="result-card-title">Inductance</div>';
    html += `
      <div class="result-item">
        <span class="result-label">L per km</span>
        <span class="result-value">${p.L_per_km.toFixed(6)} mH/km</span>
      </div>
      <div class="result-item param-highlight">
        <span class="result-label">Total Inductance</span>
        <span class="result-value">${p.L_total.toFixed(4)} mH</span>
      </div>
      <div class="result-item">
        <span class="result-label">Inductive Reactance (X<sub>L</sub>)</span>
        <span class="result-value">${p.XL.toFixed(4)} Ω</span>
      </div>`;
    html += '</div>';
    
    html += '<div class="result-card"><div class="result-card-title">Capacitance</div>';
    html += `
      <div class="result-item">
        <span class="result-label">C per km</span>
        <span class="result-value">${p.C_per_km.toFixed(6)} nF/km</span>
      </div>
      <div class="result-item param-highlight">
        <span class="result-label">Total Capacitance</span>
        <span class="result-value">${p.C_total.toFixed(4)} µF</span>
      </div>
      <div class="result-item">
        <span class="result-label">Capacitive Reactance (X<sub>C</sub>)</span>
        <span class="result-value">${p.XC.toFixed(4)} Ω</span>
      </div>`;
    html += '</div>';
  }
  
  container.innerHTML = html;
}

// ===== Control Functions =====
async function setGMRs() {
  const A = document.getElementById('gA').value;
  const B = document.getElementById('gB').value;
  const C = document.getElementById('gC').value;
  await pywebview.api.set_gmr("A", A);
  await pywebview.api.set_gmr("B", B);
  await pywebview.api.set_gmr("C", C);
  await updateResults();
}

async function updateUnit() {
  const u = document.getElementById('unit').value;
  await pywebview.api.set_unit(u);
}

async function updateScale() {
  const sx = document.getElementById('scaleX').value;
  const sy = document.getElementById('scaleY').value;
  await pywebview.api.set_scale(sx, sy);
  scaleX = parseFloat(sx);
  scaleY = parseFloat(sy);
  updateAllPoints();
  redraw();
}

async function updateLineParams() {
  const material = document.getElementById('material').value;
  const length = document.getElementById('length').value;
  const radius = document.getElementById('radius').value;
  const freq = document.getElementById('freq').value;
  
  await pywebview.api.set_line_params(material, length, radius, freq);
  await updateResults();
}

async function clearCurrent() {
  await pywebview.api.clear_bundle(activeBundle);
  bundles[activeBundle] = [];
  lastPlacedPoint = null;
  updateAllPoints();
  redraw();
  await updateResults();
}

async function clearAll() {
  await pywebview.api.clear_all();
  bundles = {A: [], B: [], C: []};
  lastPlacedPoint = null;
  updateAllPoints();
  redraw();
  await updateResults();
}

// ===== Initialize =====
redraw();
</script>
</body>
</html>
"""

# ---------- Run ----------
if __name__ == "__main__":
    api = GMDGMRApp()
    webview.create_window(
        "Transmission Line Calculator", 
        html=html, 
        js_api=api, 
        width=1600, 
        height=900,
        resizable=True
    )
    webview.start()