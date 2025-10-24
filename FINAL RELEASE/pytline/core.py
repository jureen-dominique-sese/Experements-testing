"""
Core mathematical and physics functions for GMR and GMD calculations.
"""

import numpy as np
from itertools import combinations, product

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
    if not values:
        return 1.0  # Return 1 for empty product
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
    if n == 0:
        return 1.0  # Avoid errors on empty bundles
    if n == 1:
        return r_self
    
    # Distances between every unique pair of conductors in the bundle
    distances = [distance(p1, p2) for p1, p2 in combinations(bundle_points, 2)]
    
    # The GMR formula involves n^2 terms in the root.
    # This includes n terms of r_self and n*(n-1) distances between conductors
    # (with each distance counted twice, D_12 and D_21).
    num_terms = n**2
    
    if not distances: # Should only happen if n=1, but as a safeguard
        product_of_distances = 1.0
    else:
        product_of_distances = np.prod(distances)
        
    all_terms_product = (r_self**n) * (product_of_distances**2)
    
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
    if not bundle1 or not bundle2:
        return 1.0 # Avoid errors on empty bundles
    
    distances = [distance(p1, p2) for p1, p2 in product(bundle1, bundle2)]
    return geometric_mean(distances)