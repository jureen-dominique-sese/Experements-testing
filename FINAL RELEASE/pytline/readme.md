# Transmission Line Parameter Calculator

A Python library for calculating the Geometric Mean Radius (GMR), Geometric Mean Distance (GMD), and R, L, C parameters for multi-conductor 3-phase transmission lines.

## Features

-   Calculate GMR for bundled conductors.
-   Calculate GMD between phase bundles.
-   Calculate total line Resistance (R), Inductance (L), and Capacitance (C).
-   Calculate total Inductive (XL) and Capacitive (XC) Reactance.
-   Supports multiple units (m, ft, inch, cm, mm).
-   Keeps a history of all calculations.

## Installation

1.  Make sure you have the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Place the `transmission_line_calculator` directory in your project's root folder, or in your Python's `site-packages` directory to make it globally available.

## How to Use

Here is a basic example of how to import and use the library in your own Python script.

```python
from transmission_line_calculator import TransmissionLineCalculator
import pprint

# 1. Initialize the calculator
calc = TransmissionLineCalculator()

# 2. Set line parameters
calc.set_line_params(
    material="ACSR",
    length_km=150.0,
    conductor_radius_m=0.015,
    freq_hz=60.0
)

# 3. Set the unit for coordinates
calc.set_unit("m")

# 4. Define the self GMR (r') for the conductors
#    (e.g., 0.011m, in the current unit 'm')
calc.set_self_gmr("A", 0.011)
calc.set_self_gmr("B", 0.011)
calc.set_self_gmr("C", 0.011)

# 5. Add conductor coordinates for a 3-phase horizontal line
#    Phase A at (-5, 10)
#    Phase B at (0, 10)
#    Phase C at (5, 10)
calc.add_point(x=-5, y=10, bundle="A")
calc.add_point(x=0,  y=10, bundle="B")
calc.add_point(x=5,  y=10, bundle="C")

# 6. Compute the results
results = calc.compute_results()

# 7. Print the final parameters
pprint.pprint(results['params'])

# --- Example 2: Bundled Conductors ---

calc.clear_all()
calc.set_unit("ft") # Use feet

# Set self GMR (r') = 0.0435 ft
r_prime_ft = 0.0435
calc.set_self_gmr("A", r_prime_ft)
calc.set_self_gmr("B", r_prime_ft)
calc.set_self_gmr("C", r_prime_ft)

# Phase A (2-conductor bundle, 1.5 ft spacing)
calc.add_point(x=-20, y=30, bundle="A")
calc.add_point(x=-20, y=31.5, bundle="A")

# Phase B (2-conductor bundle, 1.5 ft spacing)
calc.add_point(x=0, y=30, bundle="B")
calc.add_point(x=0, y=31.5, bundle="B")

# Phase C (2-conductor bundle, 1.5 ft spacing)
calc.add_point(x=20, y=30, bundle="C")
calc.add_point(x=20, y=31.5, bundle="C")

bundled_results = calc.compute_results()
print("\n--- Bundled Results ---")
pprint.pprint(bundled_results['params'])