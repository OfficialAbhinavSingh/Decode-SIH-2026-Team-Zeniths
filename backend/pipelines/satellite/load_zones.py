"""Load zones.geojson into the `zones` table. Run before any signal ingest.

    cd backend
    python -m pipelines.satellite.load_zones ../data/samples/zones.geojson

Idempotent: re-running upserts on zone_id, so a corrected geojson (renamed ward, fixed
pipe length) just overwrites the existing rows instead of duplicating them.

Centroid is the plain average of the exterior ring's vertices, not an area-weighted
centroid -- fine at this scale (~1.3 km near-square cells) and keeps this dependency-free
(no shapely), matching the rest of the project's "no PostGIS" MVP stance.

Handles Polygon and MultiPolygon. Real ward boundaries are often MultiPolygon -- a ward
split by a river or a railway line -- so the sample grid is not the only shape this sees.
"""

import argparse
import json

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Zone


def _ring_points(ring: list) -> list:
    """Drop the repeated closing vertex so it is not counted twice."""
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def centroid(geometry: dict) -> tuple[float, float]:
    """Average the exterior-ring vertices of a Polygon or every part of a MultiPolygon.

    Parts are not area-weighted, so a MultiPolygon whose parts differ wildly in vertex
    count pulls toward the denser part. Good enough for a map marker; it is never used
    for a spatial query.
    """
    kind = geometry.get("type")
    if kind == "Polygon":
        rings = [geometry["coordinates"][0]]
    elif kind == "MultiPolygon":
        rings = [part[0] for part in geometry["coordinates"]]
    else:
        raise ValueError(
            f"unsupported geometry type {kind!r} -- expected Polygon or MultiPolygon"
        )

    points = [point for ring in rings for point in _ring_points(ring)]
    if not points:
        raise ValueError("geometry has no coordinates")
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return lat, lon


def read_zones(path: str) -> list[dict]:
    with open(path) as fh:
        data = json.load(fh)

    zones = []
    for feature in data["features"]:
        props = feature["properties"]
        lat, lon = centroid(feature["geometry"])
        zones.append(
            {
                "id": props["zone_id"],
                "name": props["name"],
                "city": props["city"],
                "ward": props.get("ward"),
                "centroid_lat": lat,
                "centroid_lon": lon,
                "geojson": feature["geometry"],
                "pipe_length_km": props.get("pipe_length_km"),
                "population": props.get("population"),
            }
        )
    return zones


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geojson_path")
    parser.add_argument("--dry-run", action="store_true", help="parse and print, don't write")
    args = parser.parse_args()

    zones = read_zones(args.geojson_path)
    if not zones:
        print(f"no features in {args.geojson_path} -- nothing to load")
        return 1
    print(f"parsed {len(zones)} zones from {args.geojson_path}")
    for z in zones[:5]:
        print(f"  {z['id']}  {z['name']}  ({z['centroid_lat']:.4f}, {z['centroid_lon']:.4f})")

    if args.dry_run:
        return 0

    db = SessionLocal()
    try:
        update_cols = {c: getattr(insert(Zone).excluded, c) for c in zones[0] if c != "id"}
        stmt = insert(Zone).values(zones).on_conflict_do_update(
            index_elements=["id"], set_=update_cols
        )
        db.execute(stmt)
        db.commit()
    finally:
        db.close()
    print(f"upserted {len(zones)} zones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
