"""
Defines constants used throughout the transmission line calculator.
"""

# Unit conversions to meters
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