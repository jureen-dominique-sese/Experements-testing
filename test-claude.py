import numpy as np
import webview
from itertools import combinations, product

# ---------- Unit & Material Data ----------
UNIT_CONVERSIONS = {"m": 1.0, "ft": 0.3048, "inch": 0.0254, "cm": 0.01, "mm": 0.001}
MATERIALS = {"Copper": 1.68e-8, "Aluminum": 2.82e-8, "Steel": 1.43e-7, "ACSR": 3.2e-8}

# ---------- Math Utilities ----------
def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

def geometric_mean(values):
    return np.prod(values) ** (1 / len(values))

def compute_gmr(bundle_points, r_self):
    n = len(bundle_points)
    if n == 1: return r_self
    distances = [distance(p1, p2) for p1, p2 in combinations(bundle_points, 2)]
    all_terms = [r_self] * n + distances
    return np.prod(all_terms) ** (1 / n)

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
        self.material = "Copper"
        self.length = 100.0
        self.conductor_radius = 0.01
        self.freq = 60.0
        self.snap_enabled = False
        self.snap_tolerance = 0.5

    def set_snap(self, enabled):
        self.snap_enabled = enabled
        return "Snap enabled" if enabled else "Snap disabled"

    def get_snap_point(self, x, y):
        if not self.snap_enabled:
            return None
        x, y = float(x), float(y)
        # Snap to nearest integer
        snapped_x = round(x)
        snapped_y = round(y)
        return {"x": snapped_x, "y": snapped_y}

    def set_unit(self, u):
        self.unit = u
        return f"Units: {u}"

    def set_scale(self, sx, sy):
        self.scale_x, self.scale_y = float(sx), float(sy)
        return "Scale updated"

    def set_gmr(self, bundle, val):
        self.r_self[bundle] = float(val) * UNIT_CONVERSIONS[self.unit]
        return f"GMR {bundle} set"

    def set_line_params(self, material, length, radius, freq):
        self.material, self.length, self.conductor_radius, self.freq = material, float(length), float(radius), float(freq)
        return "Params updated"

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
        
        for label, points in self.bundles.items():
            if points:
                gmr_values[label] = compute_gmr(points, self.r_self[label])
                results["gmr"].append({"label": label, "value": gmr_values[label], "count": len(points)})
        
        gmd_values = {}
        for (a, b) in combinations(self.bundles.keys(), 2):
            if self.bundles[a] and self.bundles[b]:
                gmd = compute_gmd(self.bundles[a], self.bundles[b])
                gmd_values[f"{a}-{b}"] = gmd
                results["gmd"].append({"pair": f"{a}-{b}", "value": gmd})
        
        if len(gmr_values) >= 1:
            rho = MATERIALS.get(self.material, 1.68e-8)
            area = np.pi * (self.conductor_radius ** 2)
            n_conductors = max(len(self.bundles[b]) for b in self.bundles if self.bundles[b])
            R_per_km = (rho * 1000) / (area * n_conductors) if n_conductors > 0 else 0
            R_total = R_per_km * self.length
            
            if len(gmr_values) >= 2:
                avg_gmd = np.mean(list(gmd_values.values())) if gmd_values else 1.0
                avg_gmr = np.mean(list(gmr_values.values()))
                L_per_km = 2e-7 * np.log(avg_gmd / avg_gmr) * 1000
                L_total = L_per_km * self.length
                r_equiv = self.conductor_radius * (n_conductors ** 0.5) if n_conductors > 0 else self.conductor_radius
                C_per_km = (2 * np.pi * 8.854e-12 * 1000) / np.log(avg_gmd / r_equiv)
                C_total = C_per_km * self.length
            else:
                L_per_km = L_total = C_per_km = C_total = 0
            
            omega = 2 * np.pi * self.freq
            XL = omega * L_total if L_total > 0 else 0
            XC = (1 / (omega * C_total)) if C_total > 0 else 0
            
            results["params"] = {
                "R_per_km": R_per_km, "R_total": R_total,
                "L_per_km": L_per_km * 1000, "L_total": L_total * 1000,
                "C_per_km": C_per_km * 1e9, "C_total": C_total * 1e6,
                "XL": XL, "XC": XC
            }
        
        return results

# ---------- Compact HTML UI ----------
html = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Transmission Line Calculator</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
:root{--bg:#f3f3f3;--panel:#fff;--fg:#1f1f1f;--fg2:#605e5c;--accent:#0078d4;--border:#e1dfdd}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;height:100vh;overflow:hidden}
.titlebar{background:var(--panel);border-bottom:1px solid var(--border);padding:10px 16px;font-size:12px;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.app{flex:1;display:flex;overflow:hidden}
.panel{background:var(--panel);border-right:1px solid var(--border);overflow-y:auto}
.resizer{width:4px;background:var(--border);cursor:col-resize;transition:background .2s}
.resizer:hover{background:var(--accent)}
.section{padding:16px;border-bottom:1px solid var(--border)}
.section-title{font-size:11px;font-weight:600;color:var(--fg2);text-transform:uppercase;margin-bottom:12px;letter-spacing:.5px}
.form-group{margin-bottom:12px}
.form-label{display:block;font-size:11px;font-weight:500;margin-bottom:4px}
.form-control{width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:4px;font:inherit;font-size:11px}
.form-control:focus{outline:none;border-color:var(--accent)}
.form-row{display:flex;gap:8px}
.btn{padding:6px 12px;border:none;border-radius:4px;font:inherit;font-size:11px;font-weight:500;cursor:pointer;transition:all .15s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:#106ebe}
.btn-danger{background:#d13438;color:#fff}
.btn-danger:hover{background:#a72828}
.btn-sm{padding:4px 8px;font-size:10px}
.btn-block{width:100%}
.bundle-selector{display:flex;gap:6px;margin-bottom:12px}
.bundle-btn{flex:1;padding:8px;border:2px solid var(--border);border-radius:4px;background:var(--panel);font-weight:600;cursor:pointer}
.bundle-btn.active{border-color:var(--accent);color:var(--accent)}
.bundle-btn[data-bundle="A"].active{border-color:#d83b01;color:#d83b01}
.bundle-btn[data-bundle="B"].active{border-color:#0078d4;color:#0078d4}
.bundle-btn[data-bundle="C"].active{border-color:#107c10;color:#107c10}
.canvas-area{flex:1;display:flex;flex-direction:column;background:#fafafa}
.toolbar{background:var(--panel);border-bottom:1px solid var(--border);padding:8px 12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.toolbar-group{display:flex;align-items:center;gap:6px;padding:4px 8px;background:#f9f9f9;border-radius:4px;border:1px solid var(--border)}
.toolbar-label{font-size:10px;font-weight:500;color:var(--fg2)}
.toolbar-input{width:50px;padding:3px 5px;border:1px solid var(--border);border-radius:3px;font-size:10px}
.canvas-wrapper{flex:1;display:flex;align-items:center;justify-content:center;padding:20px;position:relative}
canvas{background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);cursor:crosshair}
.coord-display{position:absolute;bottom:24px;left:24px;background:rgba(0,0,0,.85);color:#fff;padding:6px 10px;border-radius:4px;font:10px monospace;opacity:0;transition:opacity .2s}
.legend{position:absolute;top:24px;right:24px;background:#fff;border:1px solid var(--border);border-radius:6px;padding:10px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.legend-title{font-size:10px;font-weight:600;color:var(--fg2);text-transform:uppercase;margin-bottom:8px}
.legend-item{display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:11px}
.legend-color{width:10px;height:10px;border-radius:50%}
.result-card{background:#f9f9f9;border:1px solid var(--border);border-radius:6px;padding:12px;margin-bottom:12px}
.result-card-title{font-size:11px;font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.result-item{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:11px}
.result-item:last-child{border:none}
.result-value{font:11px monospace;font-weight:600;color:var(--accent)}
.checkbox-label{display:flex;align-items:center;gap:6px;font-size:11px;cursor:pointer}
input[type="checkbox"]{cursor:pointer}
</style>
</head><body>
<div class="titlebar">⚡ Transmission Line Parameter Calculator</div>
<div class="app">
  <div class="panel" id="leftPanel" style="width:280px">
    <div class="section">
      <div class="section-title">Active Bundle</div>
      <div class="bundle-selector">
        <button class="bundle-btn active" data-bundle="A" onclick="setBundle('A')">A</button>
        <button class="bundle-btn" data-bundle="B" onclick="setBundle('B')">B</button>
        <button class="bundle-btn" data-bundle="C" onclick="setBundle('C')">C</button>
      </div>
      <div class="form-row">
        <button class="btn btn-danger btn-sm btn-block" onclick="clearCurrent()">Clear</button>
        <button class="btn btn-danger btn-sm btn-block" onclick="clearAll()">Clear All</button>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Geometry</div>
      <div class="form-group">
        <label class="form-label">Units</label>
        <select id="unit" class="form-control" onchange="updateUnit()">
          <option value="m">Meters</option><option value="ft">Feet</option><option value="inch">Inches</option>
          <option value="cm">Centimeters</option><option value="mm">Millimeters</option>
        </select>
      </div>
      <div class="form-row">
        <div class="form-group" style="flex:1"><label class="form-label">GMR A</label><input id="gA" type="number" step="0.001" value="0.01" class="form-control" style="font-size:10px"></div>
        <div class="form-group" style="flex:1"><label class="form-label">GMR B</label><input id="gB" type="number" step="0.001" value="0.01" class="form-control" style="font-size:10px"></div>
        <div class="form-group" style="flex:1"><label class="form-label">GMR C</label><input id="gC" type="number" step="0.001" value="0.01" class="form-control" style="font-size:10px"></div>
      </div>
      <button class="btn btn-primary btn-sm btn-block" onclick="setGMRs()">Apply GMR</button>
      <div class="form-group" style="margin-top:12px">
        <label class="checkbox-label"><input type="checkbox" id="snapToggle" onchange="toggleSnap()"> Snap to Points</label>
      </div>
    </div>
    <div class="section">
      <div class="section-title">Line Parameters</div>
      <div class="form-group"><label class="form-label">Material</label>
        <select id="material" class="form-control"><option>Copper</option><option>Aluminum</option><option>Steel</option><option>ACSR</option></select>
      </div>
      <div class="form-group"><label class="form-label">Length (km)</label><input id="length" type="number" value="100" class="form-control"></div>
      <div class="form-group"><label class="form-label">Radius (m)</label><input id="radius" type="number" step="0.001" value="0.01" class="form-control"></div>
      <div class="form-group"><label class="form-label">Frequency (Hz)</label><input id="freq" type="number" value="60" class="form-control"></div>
      <button class="btn btn-primary btn-block" onclick="updateParams()">Calculate</button>
    </div>
  </div>
  <div class="resizer" id="leftResizer"></div>
  <div class="canvas-area">
    <div class="toolbar">
      <div class="toolbar-group">
        <span class="toolbar-label">Scale X:</span><input id="scaleX" type="number" value="40" class="toolbar-input">
        <span class="toolbar-label">Y:</span><input id="scaleY" type="number" value="40" class="toolbar-input">
        <button class="btn btn-primary btn-sm" onclick="updateScale()">Apply</button>
      </div>
      <div style="margin-left:auto;font-size:10px;color:var(--fg2)">Click canvas to place • Lines show distances</div>
    </div>
    <div class="canvas-wrapper">
      <canvas id="plane" width="900" height="650"></canvas>
      <div class="coord-display" id="coordDisplay"></div>
      <div class="legend">
        <div class="legend-title">Bundles</div>
        <div class="legend-item"><div class="legend-color" style="background:#d83b01"></div>Bundle A</div>
        <div class="legend-item"><div class="legend-color" style="background:#0078d4"></div>Bundle B</div>
        <div class="legend-item"><div class="legend-color" style="background:#107c10"></div>Bundle C</div>
      </div>
    </div>
  </div>
  <div class="resizer" id="rightResizer"></div>
  <div class="panel" id="rightPanel" style="width:320px">
    <div class="section"><div class="section-title">Results</div><div id="results">Click canvas to add points</div></div>
  </div>
</div>
<script>
const canvas=document.getElementById('plane'),ctx=canvas.getContext('2d');
const colors={A:'#d83b01',B:'#0078d4',C:'#107c10'};
let bundles={A:[],B:[],C:[]},activeBundle='A',scaleX=40,scaleY=40,snapEnabled=false;
const origin={x:60,y:canvas.height-60};

function setBundle(b){activeBundle=b;document.querySelectorAll('.bundle-btn').forEach(btn=>btn.classList.toggle('active',btn.dataset.bundle===b))}

function drawGrid(){
  ctx.strokeStyle='#f5f5f5';ctx.lineWidth=1;
  for(let x=0;x<canvas.width;x+=scaleX){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);ctx.stroke()}
  for(let y=0;y<canvas.height;y+=scaleY){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(canvas.width,y);ctx.stroke()}
  
  // Axis labels with meter markings
  ctx.fillStyle='#666';ctx.font='9px Inter';
  for(let i=-2;i<=20;i++){
    if(i===0)continue;
    const x=origin.x+i*scaleX;
    ctx.fillText(i.toString(),x-5,origin.y+15);
    ctx.fillStyle='#999';
    ctx.fillText(`${(i*scaleX/40).toFixed(1)}m`,x-12,origin.y+28);
    ctx.fillStyle='#666';
  }
  for(let i=1;i<=15;i++){
    const y=origin.y-i*scaleY;
    ctx.fillText(i.toString(),origin.x-20,y+4);
    ctx.fillStyle='#999';
    ctx.fillText(`${(i*scaleY/40).toFixed(1)}m`,origin.x-45,y+4);
    ctx.fillStyle='#666';
  }
  
  ctx.strokeStyle='#424242';ctx.lineWidth=2;
  ctx.beginPath();ctx.moveTo(0,origin.y);ctx.lineTo(canvas.width,origin.y);ctx.stroke();
  ctx.beginPath();ctx.moveTo(origin.x,0);ctx.lineTo(origin.x,canvas.height);ctx.stroke();
  ctx.fillStyle='#424242';ctx.font='600 11px Inter';ctx.fillText('(0,0)',origin.x+6,origin.y-6);
}

function drawConnections(pts,color){
  if(pts.length<2)return;
  ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash([4,4]);ctx.globalAlpha=0.4;
  for(let i=0;i<pts.length;i++)for(let j=i+1;j<pts.length;j++){
    const[x1,y1]=pts[i],[x2,y2]=pts[j];
    const cx1=origin.x+x1*scaleX,cy1=origin.y-y1*scaleY,cx2=origin.x+x2*scaleX,cy2=origin.y-y2*scaleY;
    ctx.beginPath();ctx.moveTo(cx1,cy1);ctx.lineTo(cx2,cy2);ctx.stroke();
    const mx=(cx1+cx2)/2,my=(cy1+cy2)/2,dist=Math.sqrt((x2-x1)**2+(y2-y1)**2);
    ctx.globalAlpha=0.7;ctx.fillStyle=color;ctx.font='600 9px Inter';ctx.fillText(dist.toFixed(3),mx+4,my-4);ctx.globalAlpha=1;
  }
  ctx.setLineDash([]);ctx.globalAlpha=1;
}

function drawBundleCircle(pts,color){
  if(pts.length<2)return;
  let cx=0,cy=0;pts.forEach(([x,y])=>{cx+=x;cy+=y});cx/=pts.length;cy/=pts.length;
  let maxR=0;pts.forEach(([x,y])=>maxR=Math.max(maxR,Math.sqrt((x-cx)**2+(y-cy)**2)));
  const centerX=origin.x+cx*scaleX,centerY=origin.y-cy*scaleY,radius=maxR*scaleX*1.2;
  ctx.strokeStyle=color;ctx.lineWidth=2;ctx.setLineDash([8,4]);ctx.globalAlpha=0.3;
  ctx.beginPath();ctx.arc(centerX,centerY,radius,0,2*Math.PI);ctx.stroke();
  ctx.setLineDash([]);ctx.globalAlpha=1;
}

function drawBundleLines(){
  const active=['A','B','C'].filter(b=>bundles[b].length>0);
  if(active.length<2)return;
  for(let i=0;i<active.length;i++)for(let j=i+1;j<active.length;j++){
    const b1=active[i],b2=active[j];
    let cx1=0,cy1=0,cx2=0,cy2=0;
    bundles[b1].forEach(([x,y])=>{cx1+=x;cy1+=y});cx1/=bundles[b1].length;cy1/=bundles[b1].length;
    bundles[b2].forEach(([x,y])=>{cx2+=x;cy2+=y});cx2/=bundles[b2].length;cy2/=bundles[b2].length;
    const px1=origin.x+cx1*scaleX,py1=origin.y-cy1*scaleY,px2=origin.x+cx2*scaleX,py2=origin.y-cy2*scaleY;
    ctx.strokeStyle='#999';ctx.lineWidth=2;ctx.setLineDash([10,5]);ctx.globalAlpha=0.5;
    ctx.beginPath();ctx.moveTo(px1,py1);ctx.lineTo(px2,py2);ctx.stroke();
    ctx.setLineDash([]);ctx.globalAlpha=1;
  }
}

function redraw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);drawGrid();
  for(let b in bundles){drawConnections(bundles[b],colors[b]);drawBundleCircle(bundles[b],colors[b])}
  drawBundleLines();
  for(let b in bundles){
    ctx.fillStyle=colors[b];
    bundles[b].forEach(([x,y],i)=>{
      const cx=origin.x+x*scaleX,cy=origin.y-y*scaleY;
      ctx.shadowColor='rgba(0,0,0,.25)';ctx.shadowBlur=6;ctx.shadowOffsetY=2;
      ctx.beginPath();ctx.arc(cx,cy,7,0,2*Math.PI);ctx.fill();
      ctx.shadowBlur=0;ctx.shadowOffsetY=0;
      ctx.fillStyle='rgba(255,255,255,.4)';ctx.beginPath();ctx.arc(cx-1,cy-1,2,0,2*Math.PI);ctx.fill();
      ctx.fillStyle='#fff';ctx.font='600 10px Inter';const lbl=b+(i+1);
      const w=ctx.measureText(lbl).width+6;
      ctx.fillRect(cx+10,cy-14,w,16);ctx.strokeStyle=colors[b];ctx.lineWidth=1;ctx.strokeRect(cx+10,cy-14,w,16);
      ctx.fillStyle=colors[b];ctx.fillText(lbl,cx+13,cy-3);
    });
  }
}

canvas.addEventListener('click',async e=>{
  const rect=canvas.getBoundingClientRect(),mx=(e.clientX-rect.left)*canvas.width/rect.width,my=(e.clientY-rect.top)*canvas.height/rect.height;
  let x=((mx-origin.x)/scaleX),y=((origin.y-my)/scaleY);
  if(snapEnabled){const snap=await pywebview.api.get_snap_point(x,y);if(snap){x=snap.x;y=snap.y}}
  x=x.toFixed(3);y=y.toFixed(3);
  await pywebview.api.add_point(x,y,activeBundle);bundles[activeBundle].push([parseFloat(x),parseFloat(y)]);
  animatePoint(origin.x+parseFloat(x)*scaleX,origin.y-parseFloat(y)*scaleY,colors[activeBundle]);
  redraw();await updateResults();
});

canvas.addEventListener('mousemove',e=>{
  const rect=canvas.getBoundingClientRect(),mx=(e.clientX-rect.left)*canvas.width/rect.width,my=(e.clientY-rect.top)*canvas.height/rect.height;
  const x=((mx-origin.x)/scaleX).toFixed(3),y=((origin.y-my)/scaleY).toFixed(3);
  document.getElementById('coordDisplay').textContent=`x: ${x}, y: ${y}`;document.getElementById('coordDisplay').style.opacity='1';
});

canvas.addEventListener('mouseleave',()=>document.getElementById('coordDisplay').style.opacity='0');

function animatePoint(x,y,c){let r=0;const a=()=>{r+=3;if(r<30){redraw();ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.strokeStyle=c;ctx.lineWidth=3;ctx.globalAlpha=1-r/30;ctx.stroke();ctx.globalAlpha=1;requestAnimationFrame(a)}else redraw()};a()}

async function updateResults(){
  const res=await pywebview.api.compute_results(),c=document.getElementById('results');
  if(!res.gmr.length&&!res.gmd.length){c.innerHTML='<p style="color:#999;font-size:11px">Add points to see results</p>';return}
  let h='';
  if(res.gmr.length){h+='<div class="result-card"><div class="result-card-title">GMR</div>';res.gmr.forEach(r=>h+=`<div class="result-item"><span>${r.label} (${r.count})</span><span class="result-value">${r.value.toFixed(6)}m</span></div>`);h+='</div>'}
  if(res.gmd.length){h+='<div class="result-card"><div class="result-card-title">GMD</div>';res.gmd.forEach(r=>h+=`<div class="result-item"><span>${r.pair}</span><span class="result-value">${r.value.toFixed(6)}m</span></div>`);h+='</div>'}
  if(res.params&&Object.keys(res.params).length){const p=res.params;
    h+=`<div class="result-card"><div class="result-card-title">Resistance</div><div class="result-item"><span>Total R</span><span class="result-value">${p.R_total.toFixed(4)}Ω</span></div></div>`;
    h+=`<div class="result-card"><div class="result-card-title">Inductance</div><div class="result-item"><span>Total L</span><span class="result-value">${p.L_total.toFixed(4)}mH</span></div><div class="result-item"><span>X<sub>L</sub></span><span class="result-value">${p.XL.toFixed(4)}Ω</span></div></div>`;
    h+=`<div class="result-card"><div class="result-card-title">Capacitance</div><div class="result-item"><span>Total C</span><span class="result-value">${p.C_total.toFixed(4)}µF</span></div><div class="result-item"><span>X<sub>C</sub></span><span class="result-value">${p.XC.toFixed(4)}Ω</span></div></div>`;
  }
  c.innerHTML=h;
}

async function setGMRs(){await pywebview.api.set_gmr('A',document.getElementById('gA').value);await pywebview.api.set_gmr('B',document.getElementById('gB').value);await pywebview.api.set_gmr('C',document.getElementById('gC').value);await updateResults()}
async function updateUnit(){await pywebview.api.set_unit(document.getElementById('unit').value)}
async function updateScale(){scaleX=parseFloat(document.getElementById('scaleX').value);scaleY=parseFloat(document.getElementById('scaleY').value);await pywebview.api.set_scale(scaleX,scaleY);redraw()}
async function clearCurrent(){await pywebview.api.clear_bundle(activeBundle);bundles[activeBundle]=[];redraw();await updateResults()}
async function clearAll(){await pywebview.api.clear_all();bundles={A:[],B:[],C:[]};redraw();await updateResults()}
async function updateParams(){const m=document.getElementById('material').value,l=document.getElementById('length').value,r=document.getElementById('radius').value,f=document.getElementById('freq').value;await pywebview.api.set_line_params(m,l,r,f);await updateResults()}
async function toggleSnap(){snapEnabled=document.getElementById('snapToggle').checked;await pywebview.api.set_snap(snapEnabled)}

redraw();

// Panel resize functionality
let isResizing=false,currentResizer=null;
document.querySelectorAll('.resizer').forEach(r=>{
  r.addEventListener('mousedown',e=>{isResizing=true;currentResizer=r;document.body.style.cursor='col-resize';e.preventDefault()});
});
document.addEventListener('mousemove',e=>{
  if(!isResizing)return;
  if(currentResizer.id==='leftResizer'){
    const panel=document.getElementById('leftPanel'),newWidth=e.clientX-panel.offsetLeft;
    if(newWidth>200&&newWidth<500)panel.style.width=newWidth+'px';
  }else if(currentResizer.id==='rightResizer'){
    const panel=document.getElementById('rightPanel'),newWidth=window.innerWidth-e.clientX;
    if(newWidth>250&&newWidth<600)panel.style.width=newWidth+'px';
  }
});
document.addEventListener('mouseup',()=>{isResizing=false;document.body.style.cursor='default'});
</script>
</body></html>
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