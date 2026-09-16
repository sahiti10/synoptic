"""
spatial_utils.py
-----------------
Lightweight, dependency-free geospatial primitives.

The original version of this project used GeoPandas + PostGIS for spatial
querying. To keep the project installable with zero extra packages, this
module reimplements the handful of spatial operations the pipeline actually
needs, using nothing but the `math` standard library module:

    - haversine_km          -> great-circle distance between two points
    - point_in_polygon      -> ray-casting point-in-polygon test
    - point_in_multipolygon -> handles GeoJSON MultiPolygon geometries
    - polygon_centroid      -> simple centroid approximation
    - bbox_of_polygon       -> bounding box of a polygon's ring
"""

import math
from typing import List, Sequence, Tuple

Point = Tuple[float, float]  # (lon, lat) -- GeoJSON order


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometers between two lon/lat points."""
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def point_in_polygon(point: Point, ring: Sequence[Point]) -> bool:
    """
    Ray-casting point-in-polygon test for a single linear ring
    (a list of (lon, lat) tuples, GeoJSON winding not required).
    """
    x, y = point
    inside = False
    n = len(ring)
    if n < 3:
        return False
    x1, y1 = ring[0]
    for i in range(1, n + 1):
        x2, y2 = ring[i % n]
        if ((y1 > y) != (y2 > y)) and y2 != y1:
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_intersect:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def point_in_multipolygon(point: Point, geometry: dict) -> bool:
    """
    Test whether `point` (lon, lat) falls inside a GeoJSON geometry of
    type Polygon or MultiPolygon. Only the outer ring of each polygon is
    checked (holes are ignored -- sufficient for weather-alert footprints).
    """
    if not geometry:
        return False
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return False

    if gtype == "Polygon":
        outer_ring = coords[0]
        return point_in_polygon(point, outer_ring)

    if gtype == "MultiPolygon":
        for polygon in coords:
            outer_ring = polygon[0]
            if point_in_polygon(point, outer_ring):
                return True
        return False

    return False


def polygon_centroid(ring: Sequence[Point]) -> Point:
    """Arithmetic-mean centroid of a ring's vertices (good enough for
    small weather-alert polygons; not area-weighted)."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lons) / len(lons), sum(lats) / len(lats))


def geometry_centroid(geometry: dict) -> Point:
    """Centroid of a GeoJSON Polygon/MultiPolygon geometry."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        return polygon_centroid(coords[0])
    if gtype == "MultiPolygon":
        all_points: List[Point] = []
        for polygon in coords:
            all_points.extend(polygon[0])
        return polygon_centroid(all_points)
    raise ValueError(f"Unsupported geometry type: {gtype}")


def bbox_of_polygon(ring: Sequence[Point]) -> Tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) for a ring."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (min(lons), min(lats), max(lons), max(lats))
