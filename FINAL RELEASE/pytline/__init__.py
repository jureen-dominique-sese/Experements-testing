"""
Transmission Line Parameter Calculator Package

This package provides tools for calculating GMR, GMD, and R, L, C parameters
for 3-phase transmission lines.
"""

# Expose main components for easy import
from .constants import UNIT_CONVERSIONS, MATERIALS
from .core import compute_gmr, compute_gmd, distance, geometric_mean
from .calculator import pytline_calc

# Define what `from transmission_line_calculator import *` imports
__all__ = [
    'pytline_calc',
    'compute_gmr',
    'compute_gmd',
    'distance',
    'geometric_mean',
    'UNIT_CONVERSIONS',
    'MATERIALS'
]