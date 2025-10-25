import numpy as np
import webview
from itertools import combinations, product
import google.generativeai as genai
import json

GEMINI_API_KEY = "AIzaSyDgJcTZHERGt6URVGdTwd8twOCaumUtX4g"

"""
Transmission Line Parameter Calculator Backend

This script provides the backend logic for a transmission line parameter calculator.
It computes the Geometric Mean Radius (GMR), Geometric Mean Distance (GMD),
and the fundamental line parameters (Resistance, Inductance, Capacitance) for
a three-phase transmission line configuration.

The calculations support bundled conductors and various units of measurement.

Core Components:
- Utility Functions: Handle mathematical operations like distance, geometric mean,
  GMR, and GMD calculations.
- GMDGMRApp Class: An object-oriented approach to manage the state of the
  transmission line, including conductor positions, materials, and other
  physical properties.

-----------------------------
Standalone Usage Example
-----------------------------
The following example demonstrates how to use the GMDGMRApp class to model a
simple three-phase transmission line and calculate its parameters.

if __name__ == '__main__':
    # 1. Initialize the application
    app = GMDGMRApp()

    # 2. Set the units and line parameters
    print(app.set_unit("ft"))  # All coordinates and radii will be in feet
    print(app.set_line_params(material="ACSR", length=150, radius=0.04, freq=60))
    print("-" * 20)

    # 3. Define the self GMR (r') for the conductors in each phase
    # This is often given as 0.7788 * radius for a solid cylindrical wire.
    # For this example, let's use a hypothetical value.
    conductor_gmr_ft = 0.035
    print(app.set_gmr("A", conductor_gmr_ft))
    print(app.set_gmr("B", conductor_gmr_ft))
    print(app.set_gmr("C", conductor_gmr_ft))
    print("-" * 20)

    # 4. Add conductor coordinates for each phase (bundle)
    # Let's model a horizontal configuration with 20 ft spacing.
    # Phase A at (-20, 0)
    # Phase B at (0, 0)
    # Phase C at (20, 0)
    print("Adding points for Phase A...")
    app.add_point(x=-20, y=0, bundle="A")

    print("Adding points for Phase B...")
    app.add_point(x=0, y=0, bundle="B")

    print("Adding points for Phase C...")
    app.add_point(x=20, y=0, bundle="C")
    print("-" * 20)

    # 5. Compute and display the results
    results = app.compute_results()

    print("\\n========== COMPUTATION RESULTS ==========")
    print("--- GMR Values ---")
    for gmr_data in results.get("gmr", []):
        print(f"Phase {gmr_data['label']}: {gmr_data['value']:.6f} meters")

    print("\\n--- GMD Values ---")
    for gmd_data in results.get("gmd", []):
        print(f"{gmd_data['pair']}: {gmd_data['value']:.6f} meters")

    print("\\n--- Line Parameters ---")
    params = results.get("params", {})
    if params:
        print(f"Total Resistance (R): {params['R_total']:.4f} Ω")
        print(f"Total Inductance (L): {params['L_total']:.4f} mH")
        print(f"Total Capacitance (C): {params['C_total']:.4f} µF")
        print(f"Inductive Reactance (XL): {params['XL']:.4f} Ω")
        print(f"Capacitive Reactance (XC): {params['XC']:.4f} Ω")
    print("========================================")

"""

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
    """Calculates the Euclidean distance between two points.

    Args:
        p1 (tuple): A tuple (x, y) representing the first point.
        p2 (tuple): A tuple (x, y) representing the second point.

    Returns:
        float: The distance between p1 and p2.
    """
    return np.linalg.norm(np.array(p1) - np.array(p2))

def geometric_mean(values):
    """Calculates the geometric mean of a list of numbers.

    Args:
        values (list of float): A list of numerical values.

    Returns:
        float: The geometric mean of the values.
    """
    return np.prod(values) ** (1 / len(values))

def compute_gmr(bundle_points, r_self):
    """Computes the Geometric Mean Radius (GMR) for a bundled conductor.
    Also known as self GMD (Ds).

    Args:
        bundle_points (list of tuples): A list of (x, y) coordinates for each
                                        conductor within the bundle.
        r_self (float): The self GMR of a single conductor, often denoted as r'
                        (r' = 0.7788 * radius for a solid wire). Must be in meters.

    Returns:
        float: The calculated GMR of the bundle in meters.
    """
    n = len(bundle_points)
    if n == 1:
        return r_self
    # Distances between every unique pair of conductors in the bundle
    distances = [distance(p1, p2) for p1, p2 in combinations(bundle_points, 2)]
    # The GMR formula involves n^2 terms in the root.
    # This includes n terms of r_self and n*(n-1) distances between conductors
    # (with each distance counted twice, D_12 and D_21).
    # This simplified version uses each unique distance twice.
    num_terms = n**2
    all_terms_product = (r_self**n) * (np.prod(distances)**2)
    gmr = all_terms_product**(1 / num_terms)
    return gmr


def compute_gmd(bundle1, bundle2):
    """Computes the Geometric Mean Distance (GMD) between two conductor bundles.
    Also known as mutual GMD.

    Args:
        bundle1 (list of tuples): List of (x, y) coordinates for conductors in the first bundle.
        bundle2 (list of tuples): List of (x, y) coordinates for conductors in the second bundle.

    Returns:
        float: The calculated GMD between the two bundles in meters.
    """
    distances = [distance(p1, p2) for p1, p2 in product(bundle1, bundle2)]
    return geometric_mean(distances)

# ---------- App Logic ----------
class GMDGMRApp:
    """Manages the state and calculations for the transmission line calculator."""
    def __init__(self):
        """Initializes the GMDGMRApp with default values."""
        """Initializes the GMDGMRApp with default values."""
        self.bundles = {"A": [], "B": [], "C": []}
        # Initialize with 0.7788 * default radius for solid conductors
        self.r_self = {"A": 0.01 * 0.7788, "B": 0.01 * 0.7788, "C": 0.01 * 0.7788}
        self.unit = "m"
        self.scale_x = 40
        self.scale_y = 40
        
        # Line parameters
        self.material = "Copper"
        self.length = 100.0  # km
        self.conductor_radius = 0.01  # m
        self.freq = 60.0  # Hz
        
        # History tracking
        self.calc_history = []

    def set_unit(self, u):
        """Sets the default unit for all incoming spatial measurements.

        Args:
            u (str): The unit to use ('m', 'ft', 'inch', 'cm', 'mm').

        Returns:
            str: A confirmation message.
        """
        if u in UNIT_CONVERSIONS:
            self.unit = u
        return f"Units set to {u}"

    def set_scale(self, sx, sy):
        """Sets the UI canvas scaling factors (for visualization).

        Args:
            sx (float): The scale factor for the x-axis.
            sy (float): The scale factor for the y-axis.

        Returns:
            str: A confirmation message.
        """
        self.scale_x = float(sx)
        self.scale_y = float(sy)
        return "Scales updated"

    def set_gmr(self, bundle, val):
        """Sets the self GMR (r') for conductors of a given phase/bundle.

        Args:
            bundle (str): The bundle label ('A', 'B', or 'C').
            val (float): The numerical value of the self GMR in the current units.

        Returns:
            str: A confirmation message.
        """
        gmr_value = float(val) * 0.7788 * UNIT_CONVERSIONS[self.unit]
        self.r_self[bundle] = gmr_value
        return f"Set GMR for {bundle} = {val} {self.unit} (r' = {gmr_value:.6f} m)"

    def set_line_params(self, material, length, radius, freq):
        """Sets the physical parameters of the transmission line.

        Args:
            material (str): The conductor material ("Copper", "Aluminum", etc.).
            length (float): The total length of the line in kilometers.
            radius (float): The physical radius of a single conductor in meters.
            freq (float): The system frequency in Hertz.

        Returns:
            str: A confirmation message.
        """
        self.material = material
        self.length = float(length)
        self.conductor_radius = float(radius)
        self.freq = float(freq)
        return "Parameters updated"

    def add_point(self, x, y, bundle):
        """Adds a conductor's coordinate to a specific bundle/phase.

        Args:
            x (float): The x-coordinate of the conductor in the current units.
            y (float): The y-coordinate of the conductor in the current units.
            bundle (str): The bundle label to add the point to ('A', 'B', or 'C').

        Returns:
            str: "ok" on success.
        """
        x_m = float(x) * UNIT_CONVERSIONS[self.unit]
        y_m = float(y) * UNIT_CONVERSIONS[self.unit]
        self.bundles[bundle].append((x_m, y_m))
        return "ok"

    def clear_bundle(self, bundle):
        """Clears all conductor points from a single bundle.

        Args:
            bundle (str): The bundle label to clear ('A', 'B', or 'C').

        Returns:
            str: A confirmation message.
        """
        self.bundles[bundle] = []
        return f"Cleared {bundle}"

    def clear_all(self):
        """Clears all conductor points from all bundles."""
        self.bundles = {"A": [], "B": [], "C": []}
        return "All cleared"

    def compute_results(self):
        """Performs all major calculations for the defined transmission line.

        Calculates GMR for each bundle, GMD between each pair of bundles,
        and the R, L, C line parameters based on the stored configuration.
        Stores the calculation in history with timestamp.

        Returns:
            dict: A dictionary containing the results, structured as:
            {
                "gmr": [{"label": "A", "value": 0.01, "count": 1}, ...],
                "gmd": [{"pair": "A-B", "value": 1.0}, ...],
                "params": {
                    "R_total": ...,
                    "L_total": ... (mH),
                    "C_total": ... (µF),
                    "XL": ...,
                    "XC": ...
                },
                "history": [
                    {
                        "timestamp": "2025-10-24 14:30:00",
                        "config": {
                            "unit": "m",
                            "material": "ACSR",
                            "length": 100,
                            "radius": 0.0,
                            "frequency": 60,
                            "bundles": {...}
                        },
                        "results": {...}
                    },
                    ...
                ]
            }
        """
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
                # For capacitance, we use the actual conductor radius, not GMR.
                # An equivalent radius for the bundle is needed.
                # This is a simplification; a more precise method would involve potential coefficients.
                r_bundle_equiv = (n_conductors * self.conductor_radius * (geometric_mean([distance(p1,p2) for p1,p2 in combinations(self.bundles[list(gmr_values.keys())[0]], 2)]) if n_conductors > 1 else 1)**(n_conductors-1))**(1/n_conductors) if n_conductors > 1 else self.conductor_radius
                C_per_km = (2 * np.pi * 8.854e-12 * 1000) / np.log(avg_gmd / r_bundle_equiv) # F/km
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
        
        # Add to history
        from datetime import datetime
        history_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "unit": self.unit,
                "material": self.material,
                "length": self.length,
                "radius": self.conductor_radius,
                "frequency": self.freq,
                "bundles": {k: [(x,y) for x,y in v] for k,v in self.bundles.items()},
                "r_self": self.r_self.copy()
            },
            "results": results.copy()
        }
        self.calc_history.append(history_entry)
        results["history"] = self.calc_history
        
        return results

    def get_history(self):
        """Get the calculation history.
        
        Returns:
            list: List of history entries with timestamps, configurations, and results.
        """
        return self.calc_history
        
    def clear_history(self):
        """Clear the calculation history.
        
        Returns:
            str: Confirmation message.
        """
        self.calc_history = []
        return "History cleared"

    def export_latex_solution(self, api_key=None):
        """Generates a detailed LaTeX solution document using Gemini API.
        
        Args:
            api_key (str): Google Gemini API key (optional if GEMINI_API_KEY is set)
            
        Returns:
            str: LaTeX document content or error message
        """
        try:
            # Use provided key or fall back to constant
            key = api_key if api_key else GEMINI_API_KEY
            
            if not key:
                return "Error: No API key provided"
            
            # Configure Gemini
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-pro')
            
            # Get current results
            results = self.compute_results()
            
            # Check if there's data to export
            if not any(self.bundles.values()):
                return "Error: No conductor data to export. Please add some points first."
            
            # Create detailed prompt for Gemini
            prompt = f"""You are a specialized LaTeX document generator for high-precision transmission line electromagnetic analysis. Create a mathematically rigorous document with the following data:

INPUT CONFIGURATION:
Material Properties: {self.material}
Line Parameters: Length={self.length}km, Conductor Radius={self.conductor_radius}m
Operating Frequency: {self.freq}Hz
Spatial Units: {self.unit}

Phase Bundle Coordinates (meters):
{json.dumps({k: v for k, v in self.bundles.items() if v}, indent=2)}

Geometric Mean Radii (meters):
{json.dumps(self.r_self, indent=2)}

Computational Results:
{json.dumps(results, indent=2)}

DOCUMENT STRUCTURE:
1. Title: "High-Precision Electromagnetic Analysis of Transmission Line Parameters"

2. Mathematical Framework
   - Complex electromagnetic field equations
   - Carson's equations for earth return path
   - Bundle conductor mathematical models
   - Error propagation analysis

3. Spatial Configuration Analysis
   - High-precision TikZ plots (0.1mm grid resolution)
   - Phase spacing optimization analysis
   - Bundle geometry verification
   - Symmetry deviation analysis
   - Statistical error assessment

4. Rigorous GMR/GMD Derivation
   - Bundle reduction theorems
   - Matrix formulation of geometric means
   - Error bounds for GMR/GMD calculations
   - Numerical stability analysis
   - Condition number assessment

5. Electromagnetic Parameter Computation
   - Full Maxwell equation application
   - Inductance matrix derivation
   - Capacitance matrix computation
   - Skin and proximity effect analysis
   - Frequency-dependent corrections

6. Numerical Analysis
   - Convergence criteria
   - Relative error bounds
   - Condition number assessment
   - Numerical stability verification
   - Monte Carlo error estimation

7. Results with Uncertainty Analysis
   - Parameter confidence intervals
   - Error propagation through calculations
   - Sensitivity analysis
   - Statistical significance testing

MATHEMATICAL REQUIREMENTS:
- Use exact geometric formulations
- Include error bounds for all calculations
- Show complete matrix derivations
- Provide numerical stability analysis
- Include confidence intervals

PLOTTING REQUIREMENTS:
- High-resolution TikZ plots (minimum 0.1mm grid)
- Error ellipses for coordinate uncertainty
- Phase-plane analysis plots
- Log-scale GMD relationship plots
- 3D surface plots for field distributions

FORMATTING SPECIFICATIONS:
- Document class: article with amsmath, physics, siunitx
- Additional packages: tikz-3dplot, pgfplots, uncertainties
- Font: Latin Modern Math for equations
- A4 paper, 2.5cm margins
- Header: "Advanced Electromagnetic Analysis - BCMSV Calculator 2025"
- Equation numbering with cross-references
- Full appendix with numerical methods
- Bibliography with IEEE citations

PRECISION REQUIREMENTS:
- All numerical values to 6 significant figures
- Error bounds for all measurements
- Uncertainty propagation in all calculations
- Statistical confidence intervals
- Grid snapping analysis for spatial coordinates

Generate LaTeX code that can be directly compiled with pdflatex. Ensure the document clearly explains any rectification decisions and their impact on the final results."""

            # Generate LaTeX
            response = model.generate_content(prompt)
            
            latex_content = response.text
            
            # Clean up markdown code blocks if present
            if "```latex" in latex_content:
                latex_content = latex_content.split("```latex")[1].split("```")[0].strip()
            elif "```tex" in latex_content:
                latex_content = latex_content.split("```tex")[1].split("```")[0].strip()
            elif "```" in latex_content:
                latex_content = latex_content.split("```")[1].split("```")[0].strip()
            
            return latex_content
            
        except Exception as e:
            return f"Error generating LaTeX: {str(e)}"
    def generate_pdf_from_latex(self, latex_content):
        """Generates a PDF from LaTeX content using pdflatex.
        
        Args:
            latex_content (str): The LaTeX document content
            
        Returns:
            dict: {'success': bool, 'path': str, 'error': str}
        """
        import tempfile
        import subprocess
        import os
        from tkinter import Tk, filedialog
        
        try:
            # Create temporary directory for LaTeX compilation
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write LaTeX content to file
                tex_file = os.path.join(tmpdir, 'solution.tex')
                with open(tex_file, 'w', encoding='utf-8') as f:
                    f.write(latex_content)
                
                # Compile LaTeX to PDF (run twice for proper references)
                for _ in range(2):
                    result = subprocess.run(
                        ['pdflatex', '-interaction=nonstopmode', '-output-directory', tmpdir, tex_file],
                        capture_output=True,
                        timeout=30
                    )
                
                pdf_file = os.path.join(tmpdir, 'solution.pdf')
                
                if not os.path.exists(pdf_file):
                    return {
                        'success': False,
                        'error': 'PDF compilation failed. Make sure pdflatex is installed.'
                    }
                
                # Open save dialog
                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                
                timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
                default_filename = f'transmission_line_solution_{timestamp}.pdf'
                
                save_path = filedialog.asksaveasfilename(
                    defaultextension='.pdf',
                    filetypes=[('PDF files', '*.pdf'), ('All files', '*.*')],
                    initialfile=default_filename,
                    title='Save PDF Solution'
                )
                
                root.destroy()
                
                if save_path:
                    # Copy PDF to selected location
                    import shutil
                    shutil.copy2(pdf_file, save_path)
                    
                    return {
                        'success': True,
                        'path': save_path
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Save cancelled by user'
                    }
                    
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'pdflatex not found. Please install LaTeX (TeX Live, MiKTeX, or MacTeX).'
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'PDF compilation timed out.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
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

/* Left Sidebar - INCREASED WIDTH */
.sidebar {
  width: 420px; /* Increased from 320px */
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-section {
  padding: 24px; /* Increased from 20px */
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
  margin-bottom: 18px; /* Increased from 16px */
}

.form-group {
  margin-bottom: 18px; /* Increased from 16px */
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--fg);
  margin-bottom: 8px; /* Increased from 6px */
}

.form-control {
  width: 100%;
  padding: 10px 12px; /* Increased from 8px 10px */
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
  gap: 12px; /* Increased from 10px */
}

.form-row .form-group {
  flex: 1;
}

/* Buttons */
.btn {
  padding: 10px 18px; /* Increased from 8px 16px */
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
  padding: 8px 14px; /* Increased from 6px 12px */
  font-size: 12px;
}

.btn-block {
  width: 100%;
}

/* Bundle Selector */
.bundle-selector {
  display: flex;
  gap: 10px; /* Increased from 8px */
  margin-bottom: 18px; /* Increased from 16px */
}

.bundle-btn {
  flex: 1;
  padding: 12px; /* Increased from 10px */
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
  width: 400px;
  background: var(--panel);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

/* History Panel */
.history-section {
  margin-top: auto;
  border-top: 1px solid var(--border);
}

.history-header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--panel-dark);
}

.history-title {
  font-weight: 600;
  color: var(--fg);
}

.history-clear-btn {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--fg-secondary);
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
}

.history-clear-btn:hover {
  background: var(--bg);
}

.history-list {
  padding: 12px 20px;
  max-height: 300px;
  overflow-y: auto;
}

.history-item {
  padding: 12px;
  margin-bottom: 8px;
  background: var(--bg);
  border-radius: var(--radius);
  font-size: 13px;
}

.history-timestamp {
  color: var(--fg-secondary);
  font-size: 11px;
  margin-bottom: 4px;
}

.history-config {
  font-weight: 500;
}

.history-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  color: var(--fg-secondary);
  font-size: 12px;
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
    
    <!-- NEW: Offset Placement Mode -->
    <div style="margin-top: 16px; padding: 12px; background: #f3f3f3; border-radius: 6px;">
      <label style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px; cursor: pointer;">
        <input type="checkbox" id="offsetMode" onchange="toggleOffsetMode()" style="width: 16px; height: 16px; cursor: pointer;">
        <span style="font-weight: 500; font-size: 13px;">Offset Placement Mode</span>
      </label>
      
      <div id="offsetControls" style="display: none;">
        <div class="form-group" style="margin-bottom: 12px;">
          <label class="form-label">Reference Bundle</label>
          <select id="refBundle" class="form-control">
            <option value="A">Bundle A</option>
            <option value="B">Bundle B</option>
            <option value="C">Bundle C</option>
          </select>
        </div>
        
        <div class="form-row" style="margin-bottom: 12px;">
          <div class="form-group">
            <label class="form-label">Distance</label>
            <input id="offsetDist" type="number" step="0.1" value="5" class="form-control">
          </div>
          <div class="form-group">
            <label class="form-label">Angle (°)</label>
            <input id="offsetAngle" type="number" step="1" value="0" class="form-control">
          </div>
        </div>
        
        <div style="font-size: 11px; color: var(--fg-secondary); font-style: italic; margin-bottom: 12px;">
          📍 0° = Right, 90° = Up, 180° = Left, 270° = Down
        </div>
        
        <button class="btn btn-primary btn-sm btn-block" onclick="applyOffsetPlacement()">
          Apply Offset to All Points
        </button>
      </div>
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

      <div style="font-size: 11px; color: var(--fg-secondary); margin-bottom: 12px; font-style: italic;">
         Note! GMR automatically calculated as 0.7788 × radius for solid conductors
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
    
    <!-- LaTeX Export -->
    <div class="sidebar-section">
      <div class="section-title">Export Solution</div>
      
      <div class="form-group">
        <label class="form-label">Gemini API Key</label>
        <input id="apiKey" type="password" placeholder="Enter API key" class="form-control">
      </div>
      
      <button class="btn btn-primary btn-block" onclick="exportLatex()">
        Generate LaTeX Solution
      </button>
      
      <div id="exportStatus" style="margin-top: 10px; font-size: 12px; color: var(--fg-secondary);"></div>
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
    
    <!-- History Panel -->
    <div class="history-section">
      <div class="history-header">
        <div class="history-title">Calculation History</div>
        <button id="clearHistory" class="history-clear-btn">Clear History</button>
      </div>
      <div id="historyList" class="history-list"></div>
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
let zoomLevel = 1;
let panOffset = {x: 0, y: 0};
let isPanning = false;
let lastMousePos = {x: 0, y: 0};
const origin = {x: 80, y: canvas.height - 80};

// ===== Snap & Preview System =====
const SNAP_RADIUS = 15;
const SNAP_COLOR = "#FFB900";
let snapPoint = null;
let allPoints = [];
// GMR visualization state
let hoveredGMR = null;
const GMR_COLORS = {
  A: 'rgba(216, 59, 1, 0.3)',
  B: 'rgba(0, 120, 212, 0.3)',
  C: 'rgba(16, 124, 16, 0.3)'
};
let lastPlacedPoint = null;
let mousePos = {x: 0, y: 0};
let shiftKeyPressed = false;
let referencePoint = null; // Tracks if first point was from another bundle

// Track keyboard state
let inputDialog = null;

window.addEventListener('keydown', (e) => {
  if (e.key === 'Shift') shiftKeyPressed = true;
  
  // Secret combination Alt + P + J
  if (e.altKey && e.key.toLowerCase() === 'p') {
    // Start tracking for the 'j' key
    window.pKeyPressed = true;
  }
  if (window.pKeyPressed && e.altKey && e.key.toLowerCase() === 'j') {
    window.open('https://www.youtube.com/watch?v=xvFZjo5PgG0&pp=ygUJcmljayByb2xs0gcJCQYKAYcqIYzv', '_blank');
  }
  
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

    if (e.key.toLowerCase() === 'o' && !e.ctrlKey && !e.altKey) {
    document.getElementById('offsetMode').checked = !offsetMode;
    toggleOffsetMode();
  }
  
  // 'R' key to rotate offset angle by 90°
  if (e.key.toLowerCase() === 'r' && offsetMode) {
    const angleInput = document.getElementById('offsetAngle');
    let currentAngle = parseFloat(angleInput.value) || 0;
    angleInput.value = (currentAngle + 90) % 360;
    redraw();
  }
});

window.addEventListener('keyup', (e) => {
  if (e.key === 'Shift') shiftKeyPressed = false;
  if (e.key.toLowerCase() === 'p') window.pKeyPressed = false;
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
  const worldSnapRadius = SNAP_RADIUS / zoomLevel; // ✅ Scale to world space
  let minDist = worldSnapRadius;
  
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
  referencePoint = null; // Clear reference when switching bundles
  document.querySelectorAll('.bundle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.bundle === bundle);
  });
}

// ===== Drawing Functions =====
function drawGrid() {
  const visibleArea = {
    left: -panOffset.x / zoomLevel,
    top: -panOffset.y / zoomLevel,
    right: (canvas.width - panOffset.x) / zoomLevel,
    bottom: (canvas.height - panOffset.y) / zoomLevel
  };

  let gridSpacing = 40;
  if (zoomLevel < 0.5) {
    gridSpacing = Math.ceil(40 / zoomLevel / 2) * 2;
  }

  // Draw minor grid
  ctx.strokeStyle = "#f5f5f5";
  ctx.lineWidth = 0.5;
  
  const startX = Math.floor(visibleArea.left / gridSpacing) * gridSpacing;
  const endX = Math.ceil(visibleArea.right / gridSpacing) * gridSpacing;
  const startY = Math.floor(visibleArea.top / gridSpacing) * gridSpacing;
  const endY = Math.ceil(visibleArea.bottom / gridSpacing) * gridSpacing;

  for (let x = startX; x <= endX; x += gridSpacing) {
    ctx.beginPath();
    ctx.moveTo(x, startY);
    ctx.lineTo(x, endY);
    ctx.stroke();
  }
  for (let y = startY; y <= endY; y += gridSpacing) {
    ctx.beginPath();
    ctx.moveTo(startX, y);
    ctx.lineTo(endX, y);
    ctx.stroke();
  }

  // Draw major grid
  ctx.strokeStyle = "#e0e0e0";
  ctx.lineWidth = 1;
  const majorSpacing = gridSpacing * 5;

  const startMajorX = Math.floor(visibleArea.left / majorSpacing) * majorSpacing;
  const endMajorX = Math.ceil(visibleArea.right / majorSpacing) * majorSpacing;
  const startMajorY = Math.floor(visibleArea.top / majorSpacing) * majorSpacing;
  const endMajorY = Math.ceil(visibleArea.bottom / majorSpacing) * majorSpacing;

  for (let x = startMajorX; x <= endMajorX; x += majorSpacing) {
    ctx.beginPath();
    ctx.moveTo(x, startMajorY);
    ctx.lineTo(x, endMajorY);
    ctx.stroke();
  }
  for (let y = startMajorY; y <= endMajorY; y += majorSpacing) {
    ctx.beginPath();
    ctx.moveTo(startMajorX, y);
    ctx.lineTo(endMajorX, y);
    ctx.stroke();
  }

  // Draw axes
  ctx.strokeStyle = "#424242";
  ctx.lineWidth = 2;
  ctx.shadowColor = "rgba(0,0,0,0.1)";
  ctx.shadowBlur = 4;
  
  ctx.beginPath();
  ctx.moveTo(startX, 0);
  ctx.lineTo(endX, 0);
  ctx.stroke();
  
  ctx.beginPath();
  ctx.moveTo(0, startY);
  ctx.lineTo(0, endY);
  ctx.stroke();
  
  ctx.shadowBlur = 0;

  // ✅ FIXED: Draw coordinate labels in meters
  ctx.fillStyle = "#424242";
  ctx.font = "11px Inter, sans-serif";
  ctx.textAlign = "center";
  
  // X-axis labels (convert to meters)
  for (let x = startMajorX; x <= endMajorX; x += majorSpacing) {
    if (x !== 0) {
      const meterValue = (x - origin.x) / scaleX;
      ctx.fillText(meterValue.toFixed(1), x, 20);
    }
  }
  
  // Y-axis labels (convert to meters)
  ctx.textAlign = "right";
  for (let y = startMajorY; y <= endMajorY; y += majorSpacing) {
    if (y !== 0) {
      const meterValue = (origin.y - y) / scaleY;
      ctx.fillText(meterValue.toFixed(1), -10, y + 4);
    }
  }

  // Draw origin label
  ctx.fillText("0", -10, 20);
}

function drawBundleConnections(points, color) {
  if (points.length < 2) return;
  
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = 1;
  
  // Draw line connections between consecutive points
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
  
  // Draw closing line (last point back to first point) if 3+ conductors
  if (points.length >= 3) {
    const [x1, y1] = points[points.length - 1]; // Last point
    const [x2, y2] = points[0]; // First point
    const cx1 = origin.x + x1 * scaleX;
    const cy1 = origin.y - y1 * scaleY;
    const cx2 = origin.x + x2 * scaleX;
    const cy2 = origin.y - y2 * scaleY;
    
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx1, cy1);
    ctx.lineTo(cx2, cy2);
    ctx.stroke();
    
    // Draw closing segment distance
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

function drawGMRCircles() {
  gmrCircles = []; // Reset for hover detection
  
  for (let b in bundles) {
    if (bundles[b].length === 0) continue;
    
    // Calculate bundle center
    const center = getBundleCenter(bundles[b]);
    const centerX = origin.x + center.x * scaleX;
    const centerY = origin.y - center.y * scaleY;
    
    // Get GMR value from backend (stored in meters)
    // We need to calculate the visual radius based on the GMR
    const gmrMeters = (bundles[b].length === 1) 
      ? parseFloat(document.getElementById(`g${b}`).value) * 0.7788 * UNIT_CONVERSIONS[document.getElementById('unit').value]
      : null; // For bundles, GMR is calculated differently
    
    if (!gmrMeters && bundles[b].length === 1) continue;
    
    // For single conductors, use the GMR directly
    // For bundled conductors, approximate radius as 80% of max distance from center
    let visualRadius;
    
    if (bundles[b].length === 1) {
      visualRadius = gmrMeters * scaleX * 1.5; // Scale for visibility
    } else {
      // Calculate equivalent GMR radius for bundled conductors
      let maxDist = 0;
      bundles[b].forEach(([x, y]) => {
        const dist = Math.sqrt((x - center.x) ** 2 + (y - center.y) ** 2);
        maxDist = Math.max(maxDist, dist);
      });
      visualRadius = maxDist * scaleX * 0.8;
    }
    
    // Store for hover detection
    gmrCircles.push({
      bundle: b,
      centerX: centerX,
      centerY: centerY,
      radius: visualRadius,
      gmrValue: gmrMeters,
      pointCount: bundles[b].length
    });
    
    // Determine if this GMR is hovered
    const isHovered = hoveredGMR === b;
    
    // Draw GMR circle with animation
    ctx.save();
    
    // Outer glow effect (stronger when hovered)
    if (isHovered) {
      ctx.shadowColor = colors[b];
      ctx.shadowBlur = 20;
      ctx.globalAlpha = 0.4;
      
      ctx.strokeStyle = colors[b];
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(centerX, centerY, visualRadius + 5, 0, 2 * Math.PI);
      ctx.stroke();
      
      ctx.shadowBlur = 0;
    }
    
    // Main GMR circle
    ctx.globalAlpha = isHovered ? 0.5 : 0.25;
    ctx.fillStyle = colors[b];
    ctx.beginPath();
    ctx.arc(centerX, centerY, visualRadius, 0, 2 * Math.PI);
    ctx.fill();
    
    // GMR circle border
    ctx.globalAlpha = isHovered ? 0.9 : 0.6;
    ctx.strokeStyle = colors[b];
    ctx.lineWidth = isHovered ? 3 : 2;
    ctx.setLineDash([8, 4]);
    ctx.beginPath();
    ctx.arc(centerX, centerY, visualRadius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.setLineDash([]);
    
    // Draw center marker
    ctx.globalAlpha = isHovered ? 1 : 0.7;
    ctx.fillStyle = colors[b];
    ctx.beginPath();
    ctx.arc(centerX, centerY, isHovered ? 6 : 4, 0, 2 * Math.PI);
    ctx.fill();
    
    // White center dot
    ctx.fillStyle = 'white';
    ctx.beginPath();
    ctx.arc(centerX, centerY, isHovered ? 3 : 2, 0, 2 * Math.PI);
    ctx.fill();
    
    // Draw GMR label (always visible, enhanced on hover)
    const labelY = centerY - visualRadius - (isHovered ? 25 : 15);
    
    // Label background
    ctx.globalAlpha = isHovered ? 0.98 : 0.92;
    ctx.fillStyle = 'white';
    const labelWidth = isHovered ? 110 : 90;
    const labelHeight = isHovered ? 26 : 22;
    ctx.fillRect(centerX - labelWidth/2, labelY - labelHeight/2, labelWidth, labelHeight);
    
    // Label border
    ctx.strokeStyle = colors[b];
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.strokeRect(centerX - labelWidth/2, labelY - labelHeight/2, labelWidth, labelHeight);
    
    // Label text
    ctx.globalAlpha = 1;
    ctx.fillStyle = colors[b];
    ctx.font = isHovered ? 'bold 13px Consolas, Monaco, monospace' : 'bold 11px Consolas, Monaco, monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`GMR ${b}`, centerX, labelY);
    
    // Draw detailed tooltip on hover
    if (isHovered) {
      drawGMRTooltip(b, centerX, centerY, visualRadius, gmrMeters);
    }
    
    ctx.restore();
  }
}

function drawGMRTooltip(bundle, x, y, radius, gmrValue) {
  const tooltipX = x + radius + 20;
  const tooltipY = y;
  
  // Tooltip background
  ctx.globalAlpha = 0.97;
  ctx.fillStyle = '#2c2c2c';
  ctx.fillRect(tooltipX, tooltipY - 60, 180, 120);
  
  // Tooltip border with gradient
  ctx.strokeStyle = colors[bundle];
  ctx.lineWidth = 2;
  ctx.strokeRect(tooltipX, tooltipY - 60, 180, 120);
  
  // Tooltip content
  ctx.globalAlpha = 1;
  ctx.fillStyle = 'white';
  ctx.font = 'bold 13px Inter, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  
  ctx.fillText(`Bundle ${bundle} Details`, tooltipX + 10, tooltipY - 50);
  
  ctx.font = '12px Inter, sans-serif';
  ctx.fillStyle = '#e0e0e0';
  
  const conductorCount = bundles[bundle].length;
  const gmrDisplay = gmrValue ? (gmrValue * 1000).toFixed(4) : 'N/A';
  
  ctx.fillText(`Conductors: ${conductorCount}`, tooltipX + 10, tooltipY - 25);
  ctx.fillText(`GMR: ${gmrDisplay} mm`, tooltipX + 10, tooltipY);
  ctx.fillText(`Radius: ${(radius / scaleX).toFixed(3)} m`, tooltipX + 10, tooltipY + 25);
  
  // Draw pointer line from circle to tooltip
  ctx.strokeStyle = colors[bundle];
  ctx.lineWidth = 1.5;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(tooltipX, tooltipY);
  ctx.stroke();
  ctx.setLineDash([]);
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

// Add mouseup and mouseleave handlers for panning
document.addEventListener('mouseup', (e) => {
  if (e.button === 1) { // Middle mouse button
    isPanning = false;
  }
});

canvas.addEventListener('mouseleave', () => {
  isPanning = false;
});

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Save the current context state
  ctx.save();
  
  // Apply pan and zoom transformations
  ctx.translate(panOffset.x, panOffset.y);
  ctx.scale(zoomLevel, zoomLevel);
  
  drawGrid();
  
  for (let b in bundles) {
    if (bundles[b].length > 0) {
      drawBundleCircle(bundles[b], colors[b]);
      drawBundleConnections(bundles[b], colors[b]);
    }
  }

  drawGMRCircles();
  drawGMDLines();
  drawPoints();
  drawSnapIndicator();
  drawPreviewLine();
  drawOffsetPreview(); // MOVED HERE - before ctx.restore()
  
  // Restore the context state after drawing
  ctx.restore();
  
  // Draw zoom level indicator (outside transformation)
  ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
  ctx.font = '12px Inter, sans-serif';
  ctx.fillText(`Zoom: ${(zoomLevel * 100).toFixed(0)}%`, 10, 20);
  ctx.fillText('Middle-click + drag to pan', 10, 40);
  
  // Show offset mode status (outside transformation)
  if (offsetMode) {
    ctx.fillStyle = 'rgba(142, 140, 216, 0.9)';
    ctx.fillRect(10, 50, 180, 24);
    ctx.fillStyle = 'white';
    ctx.font = 'bold 12px Inter, sans-serif';
    ctx.fillText('🎯 OFFSET MODE ACTIVE', 18, 67);
  }
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

// Zoom functionality
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  
  const rect = canvas.getBoundingClientRect();
  const mouseX = (e.clientX - rect.left) * (canvas.width / rect.width);
  const mouseY = (e.clientY - rect.top) * (canvas.height / rect.height);
  
  // Get mouse position in world coordinates (before zoom)
  const worldX = (mouseX - panOffset.x) / zoomLevel;
  const worldY = (mouseY - panOffset.y) / zoomLevel;
  
  // Calculate zoom factor
  const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
  const newZoom = zoomLevel * zoomFactor;
  
  // Limit zoom level between 0.05 and 5
  if (newZoom >= 0.05 && newZoom <= 5) {
    zoomLevel = newZoom;
    // ✅ REMOVED: scaleX = 40 * zoomLevel;
    // ✅ REMOVED: scaleY = 40 * zoomLevel;
    
    // Calculate new pan offset to keep mouse position fixed
    panOffset.x = mouseX - worldX * zoomLevel;
    panOffset.y = mouseY - worldY * zoomLevel;
    
    redraw();
  }
});

// Middle mouse button panning
canvas.addEventListener('mousedown', (e) => {
  if (e.button === 1) { // Middle mouse button
    e.preventDefault();
    isPanning = true;
    lastMousePos = {x: e.clientX, y: e.clientY};
  }
});

canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  if (isPanning) {
    const dx = e.clientX - lastMousePos.x;
    const dy = e.clientY - lastMousePos.y;
    
    panOffset.x += dx;
    panOffset.y += dy;
    
    lastMousePos = {x: e.clientX, y: e.clientY};
    redraw();
    return;  // Skip other calculations while panning
  }
  
  // Get mouse position in screen coordinates
  const screenX = (e.clientX - rect.left) * scaleFactorX;
  const screenY = (e.clientY - rect.top) * scaleFactorY;
  
  // Convert to world coordinates
  const mx = (screenX - panOffset.x) / zoomLevel;
  const my = (screenY - panOffset.y) / zoomLevel;
  
  mousePos = {x: mx, y: my};

    let foundHover = false;
  for (let gmr of gmrCircles) {
    const dx = mx - gmr.centerX;
    const dy = my - gmr.centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    if (dist <= gmr.radius) {
      hoveredGMR = gmr.bundle;
      foundHover = true;
      canvas.style.cursor = 'help';
      break;
    }
  }
  
  if (!foundHover) {
    hoveredGMR = null;
    canvas.style.cursor = 'crosshair';
  }
  
  snapPoint = findSnapPoint(mx, my);
  
  // Calculate grid coordinates relative to origin
  const x = ((mx - origin.x / zoomLevel) / (scaleX / zoomLevel)).toFixed(3);
  const y = ((origin.y / zoomLevel - my) / (scaleY / zoomLevel)).toFixed(3);
  
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
  // Ignore clicks if we were just panning
  if (isPanning) {
    return;
  }
  
  const rect = canvas.getBoundingClientRect();
  const scaleFactorX = canvas.width / rect.width;
  const scaleFactorY = canvas.height / rect.height;
  
  // Get screen coordinates
  const screenX = (e.clientX - rect.left) * scaleFactorX;
  const screenY = (e.clientY - rect.top) * scaleFactorY;
  
  // Convert to world coordinates
  const mx = (screenX - panOffset.x) / zoomLevel;
  const my = (screenY - panOffset.y) / zoomLevel;
  
  let finalPos;
  let x, y;
  let isSnappedToDifferentBundle = false;
  
  if (snapPoint) {
    x = snapPoint.coordX.toFixed(3);
    y = snapPoint.coordY.toFixed(3);
    finalPos = {x: snapPoint.x, y: snapPoint.y};
    
    // Check if we're snapping to a different bundle
    if (snapPoint.bundle !== activeBundle) {
      isSnappedToDifferentBundle = true;
    }
  } else {
    const constrainedPos = getConstrainedPoint(mx, my);
    x = ((constrainedPos.x - origin.x) / scaleX).toFixed(3);
    y = ((origin.y - constrainedPos.y) / scaleY).toFixed(3);
    finalPos = {x: constrainedPos.x, y: constrainedPos.y};
  }
  
  // Check if this is the first point of the current bundle
  const isFirstPoint = bundles[activeBundle].length === 0;
  
  // If this is the first point and snapped to different bundle, mark as reference
  if (isFirstPoint && isSnappedToDifferentBundle) {
    referencePoint = {
      x: parseFloat(x),
      y: parseFloat(y),
      bundle: activeBundle
    };
  }
  
  // If this is the second point and we have a reference point, delete the first
  if (bundles[activeBundle].length === 1 && referencePoint && referencePoint.bundle === activeBundle) {
    // Remove the reference point from backend and frontend
    bundles[activeBundle].shift(); // Remove first element
    await pywebview.api.clear_bundle(activeBundle);
    
    // Re-add all remaining points (none in this case since we just removed the only one)
    for (let point of bundles[activeBundle]) {
      await pywebview.api.add_point(point[0], point[1], activeBundle);
    }
    
    referencePoint = null; // Clear reference
  }
  
  await pywebview.api.add_point(x, y, activeBundle);
  bundles[activeBundle].push([parseFloat(x), parseFloat(y)]);
  addHistoryItem('Add Point', `Bundle ${activeBundle} at (${x}, ${y})`);
  
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
// History tracking
let history = [];

function addHistoryItem(action, details) {
  const time = new Date().toLocaleTimeString();
  const item = { time, action, details };
  history.push(item);
  updateHistoryDisplay();
}

// Export/Import functionality
function exportSession() {
  const sessionData = {
    bundles,
    history,
    settings: {
      scaleX,
      scaleY,
      zoomLevel,
      panOffset,
      unit: document.getElementById('unit').value,
      material: document.getElementById('material').value,
      length: document.getElementById('length').value,
      radius: document.getElementById('radius').value,
      freq: document.getElementById('freq').value,
      gmr: {
        A: document.getElementById('gA').value,
        B: document.getElementById('gB').value,
        C: document.getElementById('gC').value
      }
    }
  };
  
  const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `transmission-line-session-${new Date().toISOString().split('T')[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
  
  addHistoryItem('Export', 'Session exported to file');
}

function importSession() {
  document.getElementById('importFile').click();
}

async function handleImport(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    
    // Restore settings
    document.getElementById('unit').value = data.settings.unit;
    document.getElementById('material').value = data.settings.material;
    document.getElementById('length').value = data.settings.length;
    document.getElementById('radius').value = data.settings.radius;
    document.getElementById('freq').value = data.settings.freq;
    document.getElementById('gA').value = data.settings.gmr.A;
    document.getElementById('gB').value = data.settings.gmr.B;
    document.getElementById('gC').value = data.settings.gmr.C;
    document.getElementById('scaleX').value = data.settings.scaleX;
    document.getElementById('scaleY').value = data.settings.scaleY;
    
    // Update internal variables
    scaleX = data.settings.scaleX;
    scaleY = data.settings.scaleY;
    zoomLevel = data.settings.zoomLevel;
    panOffset = data.settings.panOffset;
    
    // Clear existing bundles
    await pywebview.api.clear_all();
    bundles = {A: [], B: [], C: []};
    
    // Restore bundles
    for (const [bundle, points] of Object.entries(data.bundles)) {
      for (const [x, y] of points) {
        await pywebview.api.add_point(x, y, bundle);
        bundles[bundle].push([x, y]);
      }
    }
    
    // Update everything
    await updateUnit();
    await updateLineParams();
    await setGMRs();
    
    history = data.history || [];
    updateHistoryDisplay();
    redraw();
    
    addHistoryItem('Import', 'Session imported from file');
  } catch (err) {
    console.error('Import error:', err);
    alert('Error importing session file. Please check the file format.');
  }
  
  event.target.value = ''; // Reset file input
}

function updateHistoryDisplay() {
  const container = document.getElementById('historyContainer');
  if (!container) return;
  
  const html = history.map(item => `
    <div class="history-item">
      <span class="action">${item.action}${item.details ? ': ' + item.details : ''}</span>
      <span class="time">${item.time}</span>
    </div>
  `).join('');
  
  container.innerHTML = html;
  container.scrollTop = container.scrollHeight;
}
let updateResultsTimeout = null;
let isUpdating = false;

function showCalculatingIndicator() {
  const container = document.getElementById('results');
  container.innerHTML = `
    <div style="text-align: center; padding: 40px 20px;">
      <div style="width: 40px; height: 40px; border: 3px solid #e1dfdd; border-top-color: #0078d4; border-radius: 50%; margin: 0 auto 16px; animation: spin 0.8s linear infinite;"></div>
      <p style="font-size: 13px; color: #605e5c;">Calculating...</p>
    </div>
  `;
}
async function updateResults() {
  const results = await pywebview.api.compute_results();
  const container = document.getElementById('results');
  const historyList = document.getElementById('historyList');
  
  // Update history list if we have history
  if (results.history && results.history.length > 0) {
    historyList.innerHTML = results.history.map(entry => `
      <div class="history-item">
        <div class="history-timestamp">${entry.timestamp}</div>
        <div class="history-config">
          ${entry.config.material} • ${entry.config.length}km • ${entry.config.frequency}Hz
        </div>
        <div class="history-details">
          <div>GMR: ${Object.keys(entry.config.r_self).map(k => 
            `${k}: ${entry.config.r_self[k].toFixed(6)}m`).join(', ')}</div>
          <div>Points: ${Object.keys(entry.config.bundles).map(k => 
            `${k}: ${entry.config.bundles[k].length}`).join(', ')}</div>
        </div>
      </div>
    `).join('');
  }
  
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
  addHistoryItem('Update GMR', `A: ${A}, B: ${B}, C: ${C}`);
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
  referencePoint = null; // Clear reference when clearing bundle
  updateAllPoints();
  redraw();
  await updateResults();
}

async function clearAll() {
  await pywebview.api.clear_all();
  bundles = {A: [], B: [], C: []};
  lastPlacedPoint = null;
  referencePoint = null; // Clear reference when clearing all
  updateAllPoints();
  redraw();
  
  // Reset results display immediately
  const container = document.getElementById('results');
  container.innerHTML = `
    <div class="empty-state">
      <svg class="empty-icon" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"/>
      </svg>
      <p class="empty-text">Click on the canvas to place conductor points • Hold SHIFT for 90° constraints</p>
    </div>`;
    
  await updateResults();
}
// ===== LaTeX Export =====
let currentLatexContent = null;

async function exportLatex() {
  const apiKey = document.getElementById('apiKey').value;
  const statusDiv = document.getElementById('exportStatus');
  
  if (!apiKey) {
    statusDiv.style.color = '#d13438';
    statusDiv.textContent = '⚠️ Please enter your Gemini API key';
    return;
  }
  
  // Show loading modal
  showLoadingModal();
  
  try {
    const latex = await pywebview.api.export_latex_solution(apiKey);
    
    closeLoadingModal();
    
    if (latex.startsWith('Error')) {
      showResultModal('error', 'Generation Failed', latex);
    } else {
      showLatexModal(latex);
    }
  } catch (error) {
    closeLoadingModal();
    showResultModal('error', 'Export Failed', error.toString());
  }
}

function showLoadingModal() {
  const modal = document.createElement('div');
  modal.id = 'export-loading-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(4px);
  `;
  
  modal.innerHTML = `
    <div style="
      background: white;
      border-radius: 12px;
      padding: 40px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      text-align: center;
      max-width: 400px;
      animation: modalFadeIn 0.3s ease;
    ">
      <div style="
        width: 60px;
        height: 60px;
        border: 4px solid #e1dfdd;
        border-top-color: #0078d4;
        border-radius: 50%;
        margin: 0 auto 24px;
        animation: spin 1s linear infinite;
      "></div>
      
      <h3 style="
        font-size: 18px;
        font-weight: 600;
        color: #1f1f1f;
        margin-bottom: 12px;
      ">Generating LaTeX Solution</h3>
      
      <p style="
        font-size: 14px;
        color: #605e5c;
        line-height: 1.6;
      ">Please wait while Gemini AI creates your detailed step-by-step solution document...</p>
      
      <div style="
        margin-top: 20px;
        padding: 12px;
        background: #f3f3f3;
        border-radius: 6px;
        font-size: 12px;
        color: #605e5c;
      ">⏱️ This usually takes 5-15 seconds</div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Add animations if not already added
  if (!document.getElementById('modal-animations')) {
    const style = document.createElement('style');
    style.id = 'modal-animations';
    style.textContent = `
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
      @keyframes modalFadeIn {
        from { opacity: 0; transform: scale(0.9); }
        to { opacity: 1; transform: scale(1); }
      }
      @keyframes modalFadeOut {
        from { opacity: 1; transform: scale(1); }
        to { opacity: 0; transform: scale(0.9); }
      }
    `;
    document.head.appendChild(style);
  }
}

function closeLoadingModal() {
  const modal = document.getElementById('export-loading-modal');
  if (modal) {
    modal.style.animation = 'modalFadeOut 0.3s ease';
    setTimeout(() => modal.remove(), 300);
  }
}

function showResultModal(type, title, message) {
  const isSuccess = type === 'success';
  const icon = isSuccess ? '✅' : '❌';
  const color = isSuccess ? '#107c10' : '#d13438';
  
  const modal = document.createElement('div');
  modal.id = 'export-result-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(4px);
    animation: modalFadeIn 0.3s ease;
  `;
  
  modal.innerHTML = `
    <div style="
      background: white;
      border-radius: 12px;
      padding: 40px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      text-align: center;
      max-width: 450px;
      animation: modalFadeIn 0.3s ease;
    ">
      <div style="
        font-size: 48px;
        margin-bottom: 20px;
      ">${icon}</div>
      
      <h3 style="
        font-size: 20px;
        font-weight: 600;
        color: ${color};
        margin-bottom: 16px;
      ">${title}</h3>
      
      <p style="
        font-size: 14px;
        color: #605e5c;
        line-height: 1.6;
        margin-bottom: 24px;
      ">${message}</p>
      
      <button onclick="closeResultModal()" style="
        padding: 12px 32px;
        background: ${color};
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
      " onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">
        Close
      </button>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeResultModal();
    }
  });
}

function closeResultModal() {
  const modal = document.getElementById('export-result-modal');
  if (modal) {
    modal.style.animation = 'modalFadeOut 0.3s ease';
    setTimeout(() => modal.remove(), 300);
  }
}

function showLatexModal(latexContent) {
  currentLatexContent = latexContent;
  
  const modal = document.createElement('div');
  modal.id = 'latex-display-modal';
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(4px);
    animation: modalFadeIn 0.3s ease;
  `;
  
  modal.innerHTML = `
    <div style="
      background: white;
      border-radius: 12px;
      padding: 0;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      max-width: 900px;
      width: 90%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      animation: modalFadeIn 0.3s ease;
    ">
      <!-- Header -->
      <div style="
        padding: 24px 32px;
        border-bottom: 1px solid #e1dfdd;
        display: flex;
        align-items: center;
        justify-content: space-between;
      ">
        <div>
          <h3 style="
            font-size: 20px;
            font-weight: 600;
            color: #1f1f1f;
            margin-bottom: 4px;
          ">✅ LaTeX Solution Generated</h3>
          <p style="
            font-size: 13px;
            color: #605e5c;
          ">Select and copy the LaTeX code below, or download it as a .tex file</p>
        </div>
        <button class="close-latex-btn" style="
          width: 32px;
          height: 32px;
          border: none;
          background: transparent;
          color: #605e5c;
          font-size: 24px;
          cursor: pointer;
          border-radius: 4px;
          transition: all 0.15s ease;
          line-height: 1;
        " onmouseover="this.style.background='#f3f3f3'" onmouseout="this.style.background='transparent'">×</button>
      </div>
      
      <!-- Content -->
      <div style="
        flex: 1;
        overflow: hidden;
        padding: 24px 32px;
        background: #f9f9f9;
        display: flex;
        flex-direction: column;
      ">
        <textarea id="latex-content-textarea" readonly style="
          flex: 1;
          background: white;
          color: #1f1f1f;
          padding: 20px;
          border: 1px solid #e1dfdd;
          border-radius: 8px;
          font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
          font-size: 13px;
          line-height: 1.6;
          resize: none;
          outline: none;
          cursor: text;
          overflow-y: auto;
        ">${latexContent}</textarea>
      </div>
      
      <!-- Footer -->
      <div style="
        padding: 20px 32px;
        border-top: 1px solid #e1dfdd;
        display: flex;
        gap: 12px;
        justify-content: flex-end;
      ">
        <button class="select-all-btn" style="
          padding: 10px 24px;
          background: #0078d4;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          gap: 8px;
        " onmouseover="this.style.background='#106ebe'" onmouseout="this.style.background='#0078d4'">
          📋 Select All
        </button>
        
        <button class="copy-latex-btn" style="
          padding: 10px 24px;
          background: #107c10;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          gap: 8px;
        " onmouseover="this.style.background='#0e6b0e'" onmouseout="this.style.background='#107c10'">
          📄 Copy to Clipboard
        </button>
        
        <button class="export-pdf-btn" style="
          padding: 10px 24px;
          background: #d83b01;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          gap: 8px;
        " onmouseover="this.style.background='#c43501'" onmouseout="this.style.background='#d83b01'">
          📑 Export as PDF
        </button>
        
        <button class="download-latex-btn" style="
          padding: 10px 24px;
          background: #8e8cd8;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          gap: 8px;
        " onmouseover="this.style.background='#7b79c4'" onmouseout="this.style.background='#8e8cd8'">
          💾 Download .tex
        </button>

        
        
        <button class="close-latex-btn2" style="
          padding: 10px 24px;
          background: #fafafa;
          color: #1f1f1f;
          border: 1px solid #e1dfdd;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
        " onmouseover="this.style.background='#f5f5f5'" onmouseout="this.style.background='#fafafa'">
          Close
        </button>
      </div>
    </div>
  `;
  
  document.body.appendChild(modal);
  
  // Get textarea element
  const textarea = document.getElementById('latex-content-textarea');
  
  // Add event listeners
  modal.querySelector('.close-latex-btn').addEventListener('click', closeLatexModal);
  modal.querySelector('.close-latex-btn2').addEventListener('click', closeLatexModal);
  
  modal.querySelector('.select-all-btn').addEventListener('click', function() {
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    
    // Visual feedback
    const btn = this;
    const originalText = btn.innerHTML;
    btn.innerHTML = '✅ Selected!';
    
    setTimeout(() => {
      btn.innerHTML = originalText;
    }, 1500);
  });
  
  modal.querySelector('.copy-latex-btn').addEventListener('click', function() {
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    
    // Copy using multiple methods for better compatibility
    try {
      // Method 1: Modern clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(currentLatexContent).then(() => {
          showCopySuccess(this);
        }).catch(() => {
          // Fallback to execCommand
          document.execCommand('copy');
          showCopySuccess(this);
        });
      } else {
        // Method 2: Old school execCommand
        document.execCommand('copy');
        showCopySuccess(this);
      }
    } catch (err) {
      alert('Failed to copy: ' + err.message);
    }
  });
  
  modal.querySelector('.download-latex-btn').addEventListener('click', function() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `transmission_line_solution_${timestamp}.tex`;
    
    const blob = new Blob([currentLatexContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    
    // Show success feedback
    const btn = this;
    const originalText = btn.innerHTML;
    btn.innerHTML = '✅ Downloaded!';
    
    setTimeout(() => {
      btn.innerHTML = originalText;
    }, 2000);
  });

  
  // Close on background click
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeLatexModal();
    }
  });
  
  // Close on ESC key
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeLatexModal();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
  
  // Focus textarea and position cursor at start
  setTimeout(() => {
    textarea.focus();
    textarea.setSelectionRange(0, 0);
  }, 100);
}

function showCopySuccess(btn) {
  const originalText = btn.innerHTML;
  btn.innerHTML = '✅ Copied!';
  btn.style.background = '#107c10';
  
  setTimeout(() => {
    btn.innerHTML = originalText;
    btn.style.background = '#107c10';
  }, 2000);
}

function closeLatexModal() {
  const modal = document.getElementById('latex-display-modal');
  if (modal) {
    modal.style.animation = 'modalFadeOut 0.3s ease';
    setTimeout(() => modal.remove(), 300);
  }
  currentLatexContent = null;
}

function copyLatexToClipboard() {
  if (!currentLatexContent) return;
  
navigator.clipboard.writeText(currentLatexContent).then(() => {
    // Show success feedback
    const btn = event.target.closest('button'); // Now 'event' is defined
    const originalText = btn.innerHTML;
    btn.innerHTML = '✅ Copied!';
    btn.style.background = '#107c10';
    
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.style.background = '#0078d4';
    }, 2000);
  }).catch(err => {
    alert('Failed to copy: ' + err);
  });
}


// ===== History Management =====
document.getElementById('clearHistory').addEventListener('click', async () => {
  await pywebview.api.clear_history();
  document.getElementById('historyList').innerHTML = '';
  await updateResults();
});
// ===== Offset Placement System =====
let offsetMode = false;

function toggleOffsetMode() {
  offsetMode = document.getElementById('offsetMode').checked;
  const controls = document.getElementById('offsetControls');
  controls.style.display = offsetMode ? 'block' : 'none';
  
  if (offsetMode) {
    // Set reference bundle to something other than active bundle
    const refSelect = document.getElementById('refBundle');
    const options = ['A', 'B', 'C'].filter(b => b !== activeBundle);
    refSelect.value = options[0];
    
    // Show instruction
    const display = document.getElementById('coordDisplay');
    display.textContent = '🎯 Offset Mode Active • Configure distance and angle';
    display.style.background = 'rgba(142, 140, 216, 0.9)';
    display.style.opacity = '1';
    
    setTimeout(() => {
      display.style.opacity = '0';
    }, 3000);
  }
  
  redraw();
}

async function applyOffsetPlacement() {
  const refBundle = document.getElementById('refBundle').value;
  const distance = parseFloat(document.getElementById('offsetDist').value);
  const angleDeg = parseFloat(document.getElementById('offsetAngle').value);
  
  // Validation
  if (!bundles[refBundle] || bundles[refBundle].length === 0) {
    alert(`Bundle ${refBundle} has no points! Please add points to the reference bundle first.`);
    return;
  }
  
  if (!distance || distance <= 0) {
    alert('Please enter a valid positive distance');
    return;
  }
  
  if (refBundle === activeBundle) {
    alert('Reference bundle cannot be the same as active bundle!');
    return;
  }
  
  // Convert angle to radians
  const angleRad = (angleDeg * Math.PI) / 180;
  
  // Calculate offset vector
  const offsetX = distance * Math.cos(angleRad);
  const offsetY = distance * Math.sin(angleRad);
  
  // Clear current bundle
  await pywebview.api.clear_bundle(activeBundle);
  bundles[activeBundle] = [];
  
  // Create offset points for each point in reference bundle
  for (let [refX, refY] of bundles[refBundle]) {
    const newX = refX + offsetX;
    const newY = refY + offsetY;
    
    await pywebview.api.add_point(newX.toFixed(3), newY.toFixed(3), activeBundle);
    bundles[activeBundle].push([newX, newY]);
  }
  
  addHistoryItem('Offset Placement', 
    `Bundle ${activeBundle} offset from ${refBundle} by ${distance} at ${angleDeg}°`);
  
  // Visual feedback
  const display = document.getElementById('coordDisplay');
  display.textContent = `✅ Created ${bundles[activeBundle].length} offset points`;
  display.style.background = 'rgba(16, 124, 16, 0.9)';
  display.style.opacity = '1';
  
  setTimeout(() => {
    display.style.opacity = '0';
  }, 3000);
  
  updateAllPoints();
  redraw();
  await updateResults();
}

function getBundleCenter(points) {
  if (points.length === 0) return {x: 0, y: 0};
  
  let sumX = 0, sumY = 0;
  points.forEach(([x, y]) => {
    sumX += x;
    sumY += y;
  });
  
  return {
    x: sumX / points.length,
    y: sumY / points.length
  };
}
// Visual preview for offset mode
// Visual preview for offset mode
function drawOffsetPreview() {
  if (!offsetMode) return;
  
  const refBundle = document.getElementById('refBundle').value;
  const distance = parseFloat(document.getElementById('offsetDist').value) || 0;
  const angleDeg = parseFloat(document.getElementById('offsetAngle').value) || 0;
  
  if (!bundles[refBundle] || bundles[refBundle].length === 0) return;
  if (refBundle === activeBundle) return;
  
  const angleRad = (angleDeg * Math.PI) / 180;
  const offsetX = distance * Math.cos(angleRad);
  const offsetY = distance * Math.sin(angleRad);
  
  // Save current state
  const prevAlpha = ctx.globalAlpha;
  const prevLineDash = ctx.getLineDash();
  
  // Draw preview points with proper styling
  ctx.globalAlpha = 0.6;
  ctx.fillStyle = colors[activeBundle];
  ctx.strokeStyle = colors[activeBundle];
  ctx.setLineDash([5, 5]);
  ctx.lineWidth = 1.5;
  
  bundles[refBundle].forEach(([refX, refY], i) => {
    const newX = refX + offsetX;
    const newY = refY + offsetY;
    
    // Calculate canvas positions (already in world coordinates, just need scaling)
    const refCanvasX = origin.x + refX * scaleX;
    const refCanvasY = origin.y - refY * scaleY;
    const newCanvasX = origin.x + newX * scaleX;
    const newCanvasY = origin.y - newY * scaleY;
    
    // Draw offset line
    ctx.beginPath();
    ctx.moveTo(refCanvasX, refCanvasY);
    ctx.lineTo(newCanvasX, newCanvasY);
    ctx.stroke();
    
    // Draw preview point
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.arc(newCanvasX, newCanvasY, 6, 0, 2 * Math.PI);
    ctx.fill();
    
    // Draw small center dot
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'white';
    ctx.beginPath();
    ctx.arc(newCanvasX, newCanvasY, 2, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = colors[activeBundle];
    ctx.globalAlpha = 0.6;
    
    // Draw distance label on first point only
    if (i === 0) {
      const midX = (refCanvasX + newCanvasX) / 2;
      const midY = (refCanvasY + newCanvasY) / 2;
      
      // Background box
      ctx.globalAlpha = 0.95;
      ctx.fillStyle = 'rgba(142, 140, 216, 0.95)';
      const boxWidth = 90;
      const boxHeight = 26;
      ctx.fillRect(midX - boxWidth/2, midY - boxHeight/2, boxWidth, boxHeight);
      
      // Border
      ctx.strokeStyle = colors[activeBundle];
      ctx.lineWidth = 1.5;
      ctx.setLineDash([]);
      ctx.strokeRect(midX - boxWidth/2, midY - boxHeight/2, boxWidth, boxHeight);
      
      // Text
      ctx.globalAlpha = 1;
      ctx.fillStyle = 'white';
      ctx.font = 'bold 11px Consolas, Monaco, monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${distance.toFixed(2)} @ ${angleDeg}°`, midX, midY);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      
      // Reset for next iteration
      ctx.setLineDash([5, 5]);
      ctx.fillStyle = colors[activeBundle];
      ctx.strokeStyle = colors[activeBundle];
      ctx.globalAlpha = 0.6;
    }
  });
  
  // Restore previous state
  ctx.globalAlpha = prevAlpha;
  ctx.setLineDash(prevLineDash);
  ctx.lineWidth = 1;
}
// ===== Initialize =====
// Add live update for offset preview
document.addEventListener('DOMContentLoaded', () => {
  const offsetDist = document.getElementById('offsetDist');
  const offsetAngle = document.getElementById('offsetAngle');
  const refBundle = document.getElementById('refBundle');
  
  if (offsetDist) {
    offsetDist.addEventListener('input', () => {
      if (offsetMode) redraw();
    });
  }
  
  if (offsetAngle) {
    offsetAngle.addEventListener('input', () => {
      if (offsetMode) redraw();
    });
  }
  
  if (refBundle) {
    refBundle.addEventListener('change', () => {
      if (offsetMode) redraw();
    });
  }
});
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