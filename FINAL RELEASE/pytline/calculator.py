"""
Main calculator class for managing transmission line state and parameters.
"""

import numpy as np
from itertools import combinations
from datetime import datetime

# Import from our own package
from . import constants
from .core import compute_gmr, compute_gmd, geometric_mean, distance

class pytline_calc:
    """Manages the state and calculations for the transmission line."""
    
    def __init__(self):
        """Initializes the calculator with default values."""
        self.bundles = {"A": [], "B": [], "C": []}
        # Default r' (self GMR) = 0.7788 * 1cm radius
        default_r_self = 0.01 * 0.7788
        self.r_self = {"A": default_r_self, "B": default_r_self, "C": default_r_self}
        self.unit = "m"
        
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
        """
        if u in constants.UNIT_CONVERSIONS:
            self.unit = u
            return f"Units set to {u}"
        else:
            raise ValueError(f"Unknown unit: {u}. Must be one of {constants.UNIT_CONVERSIONS.keys()}")

    def set_self_gmr(self, bundle, r_self_val):
        """Sets the self GMR (r') for conductors of a given phase/bundle.

        Args:
            bundle (str): The bundle label ('A', 'B', or 'C').
            r_self_val (float): The numerical value of the self GMR (r') 
                                in the **current units**.

        Returns:
            str: A confirmation message.
        """
        if bundle not in self.bundles:
            raise ValueError(f"Invalid bundle: {bundle}. Must be 'A', 'B', or 'C'.")
            
        gmr_in_meters = float(r_self_val) * constants.UNIT_CONVERSIONS[self.unit]
        self.r_self[bundle] = gmr_in_meters
        return f"Set self GMR (r') for {bundle} = {r_self_val} {self.unit} ({gmr_in_meters:.6f} m)"

    def set_line_params(self, material, length_km, conductor_radius_m, freq_hz):
        """Sets the physical parameters of the transmission line.

        Args:
            material (str): The conductor material ("Copper", "Aluminum", etc.).
            length_km (float): The total length of the line in kilometers.
            conductor_radius_m (float): The physical radius of a single conductor in meters.
            freq_hz (float): The system frequency in Hertz.

        Returns:
            str: A confirmation message.
        """
        if material not in constants.MATERIALS:
            raise ValueError(f"Unknown material: {material}. Must be one of {constants.MATERIALS.keys()}")
            
        self.material = material
        self.length = float(length_km)
        self.conductor_radius = float(conductor_radius_m)
        self.freq = float(freq_hz)
        return "Line parameters updated"

    def add_point(self, x, y, bundle):
        """Adds a conductor's coordinate to a specific bundle/phase.
        Coordinates are in the currently set unit.

        Args:
            x (float): The x-coordinate of the conductor in the current units.
            y (float): The y-coordinate of the conductor in the current units.
            bundle (str): The bundle label to add the point to ('A', 'B', or 'C').
        """
        if bundle not in self.bundles:
            raise ValueError(f"Invalid bundle: {bundle}. Must be 'A', 'B', or 'C'.")
            
        unit_factor = constants.UNIT_CONVERSIONS[self.unit]
        x_m = float(x) * unit_factor
        y_m = float(y) * unit_factor
        self.bundles[bundle].append((x_m, y_m))
        return f"Added point ({x}, {y}) {self.unit} to bundle {bundle}"

    def clear_bundle(self, bundle):
        """Clears all conductor points from a single bundle."""
        if bundle not in self.bundles:
            raise ValueError(f"Invalid bundle: {bundle}. Must be 'A', 'B', or 'C'.")
        self.bundles[bundle] = []
        return f"Cleared bundle {bundle}"

    def clear_all(self):
        """Clears all conductor points from all bundles."""
        self.bundles = {"A": [], "B": [], "C": []}
        return "All bundles cleared"

    def compute_results(self):
        """Performs all major calculations for the defined transmission line.

        Calculates GMR for each bundle, GMD between each pair of bundles,
        and the R, L, C line parameters based on the stored configuration.
        Stores the calculation in history.

        Returns:
            dict: A dictionary containing the results.
        """
        results = {"gmr": [], "gmd": [], "params": {}}
        gmr_values = {}
        
        # GMR calculations
        for label, points in self.bundles.items():
            if points:
                gmr_val = compute_gmr(points, self.r_self[label])
                gmr_values[label] = gmr_val
                results["gmr"].append({
                    "label": label,
                    "value": gmr_val,
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
        
        # --- Parameter calculations (3-phase assumed) ---
        if not gmr_values:
            return {"error": "No conductors added. Cannot calculate parameters."}

        # Find max number of conductors in any bundle for resistance calc
        n_conductors_per_phase = max(len(p) for p in self.bundles.values() if p)

        # Resistance (R)
        rho = constants.MATERIALS.get(self.material)
        area = np.pi * (self.conductor_radius ** 2)
        R_per_km = (rho * 1000) / (area * n_conductors_per_phase)
        R_total = R_per_km * self.length
        
        # Inductance (L) and Capacitance (C)
        if len(gmr_values) >= 2:
            # Symmetrical spacing assumed, using equivalent GMD and GMR
            avg_gmd = np.mean(list(gmd_values.values()))
            avg_gmr = geometric_mean(list(gmr_values.values()))
            
            # Inductance (H/km and H total)
            L_per_km = 2e-7 * np.log(avg_gmd / avg_gmr) * 1000  # H/km
            L_total = L_per_km * self.length
            
            # Capacitance (F/km and F total)
            # This is a simplification. A precise method uses potential coefficients.
            # We calculate an equivalent bundle radius for the capacitance formula.
            # We use the bundle points from the first available phase for this.
            first_bundle_points = next(p for p in self.bundles.values() if p)
            n_cb = len(first_bundle_points)

            if n_cb == 1:
                r_bundle_equiv = self.conductor_radius
            else:
                bundle_distances = [distance(p1,p2) for p1,p2 in combinations(first_bundle_points, 2)]
                r_bundle_equiv = (n_cb * self.conductor_radius * (geometric_mean(bundle_distances)**(n_cb-1)))**(1/n_cb)

            C_per_km = (2 * np.pi * 8.854e-12 * 1000) / np.log(avg_gmd / r_bundle_equiv) # F/km
            C_total = C_per_km * self.length
        else:
            # Single-phase or incomplete
            L_per_km = 0
            L_total = 0
            C_per_km = 0
            C_total = 0
            
        # Reactances
        omega = 2 * np.pi * self.freq
        XL = omega * L_total if L_total > 0 else 0
        XC = (1 / (omega * C_total)) if C_total > 0 else 0
        
        results["params"] = {
            "R_per_km_ohm": R_per_km,
            "R_total_ohm": R_total,
            "L_per_km_mH": L_per_km * 1000,  # mH/km
            "L_total_mH": L_total * 1000,  # mH
            "C_per_km_nF": C_per_km * 1e9,  # nF/km
            "C_total_uF": C_total * 1e6,  # µF
            "XL_total_ohm": XL,
            "XC_total_ohm": XC,
            "GMD_equivalent_m": avg_gmd if 'avg_gmd' in locals() else None,
            "GMR_equivalent_m": avg_gmr if 'avg_gmr' in locals() else None
        }
        
        # --- Add to history ---
        history_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "unit": self.unit,
                "material": self.material,
                "length_km": self.length,
                "radius_m": self.conductor_radius,
                "frequency_hz": self.freq,
                "bundles": {k: v[:] for k,v in self.bundles.items()}, # Deep copy
                "r_self_m": self.r_self.copy()
            },
            "results": results.copy()
        }
        self.calc_history.append(history_entry)
        results["history"] = self.calc_history
        
        return results