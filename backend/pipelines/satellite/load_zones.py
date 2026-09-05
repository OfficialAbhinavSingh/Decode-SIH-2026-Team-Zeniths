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

from app.db import SessionLocal
from app.models import Zone
from app.upsert import upsert


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


REQUIRED_PROPS = ("zone_id", "name", "city")


def _check_props(props: dict, index: int) -> None:
    """Fail with the property names, not a bare KeyError.

    Downloaded ward boundaries almost never use our names -- a JMC file calls them
    WARD_NO / WARD_NAME. Saying which key is missing and what the file actually has
    turns a stack trace into a two-minute fix.
    """
    missing = [key for key in REQUIRED_PROPS if key not in props]
    if missing:
        raise ValueError(
            f"feature {index} is missing {', '.join(missing)}; its properties are "
            f"{sorted(props)}. Rename them in the geojson before loading."
        )


def dedupe_by_id(zones: list[dict]) -> list[dict]:
    """Collapse features that repeat a zone_id, last one wins.

    Postgres rejects a batch that hits the same conflict key twice ("ON CONFLICT DO UPDATE
    command cannot affect row a second time"). A hand-edited ward file repeats an id often
    enough that surviving it beats crashing on it -- same rule the ingest endpoints use.
    """
    collapsed: dict[str, dict] = {}
    for zone in zones:
        collapsed[zone["id"]] = zone
    return list(collapsed.values())


def read_zones(path: str) -> list[dict]:
    with open(path) as fh:
        data = json.load(fh)

    zones = []
    for index, feature in enumerate(data["features"]):
        props = feature["properties"]
        _check_props(props, index)
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

    parsed = read_zones(args.geojson_path)
    if not parsed:
        print(f"no features in {args.geojson_path} -- nothing to load")
        return 1
    zones = dedupe_by_id(parsed)
    if len(zones) != len(parsed):
        print(f"warning: collapsed {len(parsed) - len(zones)} repeated zone_id(s), last one wins")
    print(f"parsed {len(zones)} zones from {args.geojson_path}")
    for z in zones[:5]:
        print(f"  {z['id']}  {z['name']}  ({z['centroid_lat']:.4f}, {z['centroid_lon']:.4f})")

    if args.dry_run:
        return 0

    db = SessionLocal()
    try:
        upsert(db, Zone, zones, index_elements=["id"])
        db.commit()
    finally:
        db.close()
    print(f"upserted {len(zones)} zones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
