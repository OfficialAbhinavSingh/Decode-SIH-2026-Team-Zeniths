"""Minimal geometry helpers. No PostGIS, no shapely -- MVP needs exactly one operation:
match a citizen's lat/lon to the zone polygon that contains it.
"""


def _ring_contains(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon over a GeoJSON linear ring ([lon, lat] pairs)."""
    inside = False
    count = len(ring)
    j = count - 1
    for i in range(count):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_at_lat = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_at_lat:
                inside = not inside
        j = i
    return inside


def point_in_geojson(lon: float, lat: float, geometry: dict) -> bool:
    """True if the point falls inside a GeoJSON Polygon or MultiPolygon.

    Handles holes: a point inside an interior ring is outside the polygon.
    """
    if not geometry:
        return False

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")
    if geom_type == "Feature":
        return point_in_geojson(lon, lat, geometry.get("geometry", {}))
    if not coords:
        return False

    if geom_type == "Polygon":
        polygons = [coords]
    elif geom_type == "MultiPolygon":
        polygons = coords
    else:
        return False

    for polygon in polygons:
        if not polygon:
            continue
        if _ring_contains(lon, lat, polygon[0]):
            in_hole = any(_ring_contains(lon, lat, hole) for hole in polygon[1:])
            if not in_hole:
                return True
    return False
