import math


# calculate GMD (Geometric Mean Distance)
if not distances or any(d <= 0 for d in distances):
        raise ValueError("All distances must be positive and non-zero.") # Ensure all distances are positive and non-zero

    n = len(distances) # number of distances
    product = reduce(lambda x, y: x * y, distances) # product of all distances (d1*d2*...*dn)
    gmd = product ** (1 / n) # given n distances, GMD = nth root of (d1*d2*...*dn)
    return gmd

# calculate GMR (Geometric Mean Radius)

#sakdlasdjlasdjalkdjadla