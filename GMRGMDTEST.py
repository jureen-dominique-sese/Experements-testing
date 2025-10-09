import numpy as np
import webview
from itertools import combinations, product

# ---------- Unit Conversion ----------
UNIT_CONVERSIONS = {
    "m": 1.0,
    "ft": 0.3048,
    "inch": 0.0254,
    "cmil": 2.54e-8,
    "kcmil": 2.54e-5
}

# ---------- Math Utilities ----------
def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

def geometric_mean(values):
    return np.prod(values) ** (1 / len(values))

def compute_gmr(bundle_points, r_self):
    """
    Compute Geometric Mean Radius for a bundle of conductors.
    
    GMR = (r' × r' × ... × D₁₂ × D₁₃ × ... × Dᵢⱼ)^(1/n)
    
    where n = number of conductors in bundle
    r' = self GMR of individual conductor
    Dᵢⱼ = mutual distances between conductors
    """
    n = len(bundle_points)
    if n == 1:
        return r_self
    
    # Calculate all mutual distances between conductors
    distances = [distance(p1, p2) for p1, p2 in combinations(bundle_points, 2)]
    
    # Build the product: r_self appears n times, plus all mutual distances
    all_terms = [r_self] * n + distances
    
    # Take the nth root of the product
    gmr = np.prod(all_terms) ** (1 / n)
    
    return gmr

def compute_gmd(bundle1, bundle2):
    """
    Compute Geometric Mean Distance between two bundles.
    
    GMD = (D₁₁ × D₁₂ × ... × Dᵢⱼ)^(1/(m×n))
    
    where m = conductors in bundle1, n = conductors in bundle2
    """
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
        results = {"gmr": [], "gmd": []}
        gmr_values = {}
        
        for label, points in self.bundles.items():
            if points:
                gmr_values[label] = compute_gmr(points, self.r_self[label])
                results["gmr"].append({
                    "label": label,
                    "value": gmr_values[label],
                    "count": len(points)
                })
        
        for (a, b) in combinations(self.bundles.keys(), 2):
            if self.bundles[a] and self.bundles[b]:
                gmd = compute_gmd(self.bundles[a], self.bundles[b])
                results["gmd"].append({
                    "pair": f"{a}-{b}",
                    "value": gmd
                })
        
        return results

# ---------- Modern Split-Panel HTML UI ----------
html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Conductor GMD/GMR Visualizer</title>
<style>
:root {
  --bg: #f5f5f5;
  --panel: #ffffff;
  --fg: #1e1e1e;
  --accent: #0078d7;
  --border: #e0e0e0;
  --shadow: 0 2px 12px rgba(0,0,0,0.08);
  --font: "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --radius: 8px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font);
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

header {
  background: linear-gradient(135deg, #0078d7 0%, #005a9e 100%);
  color: white;
  box-shadow: var(--shadow);
  padding: 16px 24px;
  font-weight: 600;
  font-size: 1.2em;
  display: flex;
  align-items: center;
  gap: 10px;
}

#toolbar {
  background: var(--panel);
  padding: 12px 24px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.06);
  z-index: 2;
  border-bottom: 1px solid var(--border);
}

#toolbar label {
  font-weight: 500;
  margin-right: 4px;
  font-size: 0.9em;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: #f9f9f9;
  border-radius: var(--radius);
}

input, select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.9em;
  background: #fff;
  transition: border 0.2s;
}

input:focus, select:focus {
  outline: none;
  border-color: var(--accent);
}

button {
  background: var(--accent);
  color: white;
  cursor: pointer;
  border: none;
  border-radius: 6px;
  padding: 7px 14px;
  font-size: 0.9em;
  font-weight: 500;
  transition: all 0.2s;
}

button:hover {
  background: #005a9e;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0,120,215,0.2);
}

button:active {
  transform: translateY(0);
}

button.danger {
  background: #d83b01;
}

button.danger:hover {
  background: #b02e00;
}

#main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

#canvas-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  position: relative;
  min-width: 500px;
}

#canvas-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

canvas {
  background: white;
  cursor: crosshair;
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  max-width: 100%;
  max-height: 100%;
}

#results-section {
  width: 380px;
  background: var(--panel);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.results-header {
  padding: 16px 20px;
  background: #f9f9f9;
  border-bottom: 2px solid var(--border);
  font-weight: 600;
  font-size: 1.05em;
  display: flex;
  align-items: center;
  gap: 8px;
}

.results-content {
  padding: 16px;
  flex: 1;
  overflow-y: auto;
}

.result-card {
  background: #f9f9f9;
  border-radius: var(--radius);
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
}

.result-card h3 {
  margin: 0 0 10px 0;
  font-size: 0.95em;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.result-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  background: white;
  border-radius: 6px;
  margin-bottom: 6px;
  align-items: center;
  border: 1px solid #eee;
}

.result-label {
  font-weight: 600;
  color: var(--fg);
  display: flex;
  align-items: center;
  gap: 6px;
}

.result-value {
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--accent);
  font-weight: 500;
}

.bundle-badge {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 2px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.empty-state svg {
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  opacity: 0.3;
}

#coord-display {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: rgba(0,0,0,0.75);
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.85em;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.legend {
  display: flex;
  gap: 16px;
  padding: 10px 20px;
  background: white;
  border-top: 1px solid var(--border);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85em;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
</style>
</head>
<body>
<header>
  <span>⚡</span>
  <span>Conductor GMD/GMR Visualizer</span>
</header>

<div id="toolbar">
  <div class="toolbar-group">
    <label>Units:</label>
    <select id="unit" onchange="updateUnit()">
      <option value="m">meters</option>
      <option value="ft">feet</option>
      <option value="inch">inch</option>
      <option value="cmil">cmil</option>
      <option value="kcmil">kcmil</option>
    </select>
  </div>

  <div class="toolbar-group">
    <label>Scale X:</label><input id="scaleX" type="number" value="40" style="width:60px;">
    <label>Y:</label><input id="scaleY" type="number" value="40" style="width:60px;">
    <button onclick="updateScale()">Apply</button>
  </div>

  <div class="toolbar-group">
    <label>Active Bundle:</label>
    <select id="bundle">
      <option value="A">A</option>
      <option value="B">B</option>
      <option value="C">C</option>
    </select>
  </div>

  <div class="toolbar-group">
    <label>GMR A:</label><input id="gA" type="number" step="0.001" value="0.01" style="width:60px;">
    <label>B:</label><input id="gB" type="number" step="0.001" value="0.01" style="width:60px;">
    <label>C:</label><input id="gC" type="number" step="0.001" value="0.01" style="width:60px;">
    <button onclick="setGMRs()">Set</button>
  </div>

  <div style="margin-left: auto; display: flex; gap: 8px;">
    <button class="danger" onclick="clearCurrent()">Clear Bundle</button>
    <button class="danger" onclick="clearAll()">Clear All</button>
  </div>
</div>

<div id="main-container">
  <div id="canvas-section">
    <div id="canvas-wrapper">
      <canvas id="plane" width="800" height="600"></canvas>
    </div>
    <div id="coord-display">x: 0.000, y: 0.000</div>
    <div class="legend">
      <div class="legend-item">
        <div class="legend-color" style="background: #d83b01;"></div>
        <span>Bundle A</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #0078d7;"></div>
        <span>Bundle B</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #107c10;"></div>
        <span>Bundle C</span>
      </div>
    </div>
  </div>

  <div id="results-section">
    <div class="results-header">
      📊 Calculation Results
    </div>
    <div class="results-content" id="results">
      <div class="empty-state">
        <svg fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"/>
        </svg>
        <p>Click on the canvas to add conductor points</p>
      </div>
    </div>
  </div>
</div>

<script>
const canvas = document.getElementById('plane');
const ctx = canvas.getContext('2d');
const colors = {A: '#d83b01', B: '#0078d7', C: '#107c10'};
let bundles = {A: [], B: [], C: []};
let scaleX = 40, scaleY = 40;
const origin = {x: 60, y: canvas.height - 60};

function drawGrid() {
  ctx.strokeStyle = "#f0f0f0";
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += scaleX) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += scaleY) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }
  
  // Axes
  ctx.strokeStyle = "#666";
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(0, origin.y); ctx.lineTo(canvas.width, origin.y); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(origin.x, 0); ctx.lineTo(origin.x, canvas.height); ctx.stroke();
  
  // Origin marker
  ctx.fillStyle = "#333";
  ctx.font = "12px monospace";
  ctx.fillText("(0,0)", origin.x + 5, origin.y - 5);
}

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawGrid();
  
  for (let b in bundles) {
    ctx.fillStyle = colors[b];
    bundles[b].forEach(([x, y], i) => {
      const cx = origin.x + x * scaleX;
      const cy = origin.y - y * scaleY;
      
      // Draw point
      ctx.beginPath();
      ctx.arc(cx, cy, 7, 0, 2*Math.PI);
      ctx.shadowColor = "rgba(0,0,0,0.2)";
      ctx.shadowBlur = 6;
      ctx.fill();
      ctx.shadowBlur = 0;
      
      // Draw label
      ctx.fillStyle = "#333";
      ctx.font = "bold 11px sans-serif";
      ctx.fillText(b + (i+1), cx + 10, cy - 8);
      ctx.fillStyle = colors[b];
    });
  }
}

canvas.addEventListener('click', async (e) => {
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  const mx = (e.clientX - rect.left) * scaleFactorX;
  const my = (e.clientY - rect.top) * scaleFactorY;
  
  const x = ((mx - origin.x) / scaleX).toFixed(3);
  const y = ((origin.y - my) / scaleY).toFixed(3);
  const bundle = document.getElementById('bundle').value;
  
  await pywebview.api.add_point(x, y, bundle);
  bundles[bundle].push([parseFloat(x), parseFloat(y)]);
  
  animatePoint(mx, my, colors[bundle]);
  redraw();
  await updateResults();
});

canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  const mx = (e.clientX - rect.left) * scaleFactorX;
  const my = (e.clientY - rect.top) * scaleFactorY;
  
  const x = ((mx - origin.x) / scaleX).toFixed(3);
  const y = ((origin.y - my) / scaleY).toFixed(3);
  
  const display = document.getElementById('coord-display');
  display.textContent = `x: ${x}, y: ${y}`;
  display.style.opacity = '1';
});

canvas.addEventListener('mouseleave', () => {
  document.getElementById('coord-display').style.opacity = '0';
});

function animatePoint(x, y, color) {
  let r = 0;
  const anim = () => {
    r += 2;
    if (r < 18) {
      redraw();
      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.strokeStyle = color;
      ctx.globalAlpha = 0.5 * (1 - r/18);
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.globalAlpha = 1;
      requestAnimationFrame(anim);
    } else redraw();
  };
  anim();
}

async function updateResults() {
  const results = await pywebview.api.compute_results();
  const container = document.getElementById('results');
  
  if (results.gmr.length === 0 && results.gmd.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"/>
        </svg>
        <p>Click on the canvas to add conductor points</p>
      </div>`;
    return;
  }
  
  let html = '';
  
  if (results.gmr.length > 0) {
    html += '<div class="result-card"><h3>Geometric Mean Radius (GMR)</h3>';
    results.gmr.forEach(r => {
      html += `
        <div class="result-item">
          <span class="result-label">
            <span class="bundle-badge" style="background:${colors[r.label]}"></span>
            Bundle ${r.label} <span style="color:#999; font-size:0.85em;">(${r.count} conductor${r.count>1?'s':''})</span>
          </span>
          <span class="result-value">${r.value.toFixed(6)} m</span>
        </div>`;
    });
    html += '</div>';
  }
  
  if (results.gmd.length > 0) {
    html += '<div class="result-card"><h3>Geometric Mean Distance (GMD)</h3>';
    results.gmd.forEach(r => {
      html += `
        <div class="result-item">
          <span class="result-label">Distance ${r.pair}</span>
          <span class="result-value">${r.value.toFixed(6)} m</span>
        </div>`;
    });
    html += '</div>';
  }
  
  container.innerHTML = html;
}

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
  redraw();
}

async function clearCurrent() {
  const bundle = document.getElementById('bundle').value;
  await pywebview.api.clear_bundle(bundle);
  bundles[bundle] = [];
  redraw();
  await updateResults();
}

async function clearAll() {
  await pywebview.api.clear_all();
  bundles = {A: [], B: [], C: []};
  redraw();
  await updateResults();
}

function init() { redraw(); }
init();
</script>
</body>
</html>
"""

# ---------- Run ----------
if __name__ == "__main__":
    api = GMDGMRApp()
    webview.create_window(
        "Conductor GMD & GMR Visualizer", 
        html=html, 
        js_api=api, 
        width=1280, 
        height=800,
        resizable=True
    )
    webview.start()