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

test = GMDGMRApp()
print(f"Value is {compute_gmd([6,1],[3,1])}")