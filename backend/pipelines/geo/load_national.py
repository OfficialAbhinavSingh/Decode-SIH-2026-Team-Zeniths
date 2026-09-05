"""Load the national city registry and zone layer into the database.

Owner: R2 (Data). Run after `registry.py` and `build_zones.py`.

    cd backend
    python -m pipelines.geo.load_national \
        --cities ../data/india/cities.csv \
        --summary ../data/india/city_summary.csv \
        --zones ../data/india/zones_india.geojson

Idempotent: upserts on `cities.code` and `zones.id`, so a corrected registry overwrites
rather than duplicating -- the same rule `load_zones.py` follows for a single city.

--replace deletes zones that are NOT in the file being loaded, together with every signal
and score row hanging off them. That is the switch between "one city, the MVP demo" and
"the whole country": without it, loading the national layer on top of the Jaipur sample
leaves the old `Z-0xx` zones sitting alongside the new `JAI-0xx` ones and Jaipur is in the
database twice under two different zone schemes. It is destructive on purpose and prints
what it is about to delete.
"""

import argparse
import json
import sys

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.upsert import upsert
from app.models import (
    BillingSignal,
    City,
    CitizenReport,
    CityScore,
    SatelliteSignal,
    Zone,
    ZoneScore,
)

from ..satellite.load_zones import centroid, dedupe_by_id

# Batch size for the delete sweep. `upsert` does its own parameter-aware chunking.
CHUNK = 500


def read_cities(cities_path: str, summary_path: str | None) -> list[dict]:
    from .registry import read_csv

    rows = read_csv(cities_path)
    summary: dict[str, dict] = {}
    if summary_path:
        import csv

        try:
            with open(summary_path, newline="") as fh:
                summary = {r["city_code"]: r for r in csv.DictReader(fh)}
        except FileNotFoundError:
            print(f"note: {summary_path} not found, loading cities without zone stats")

    out = []
    for row in rows:
        extra = summary.get(row["city_code"], {})
        out.append(
            {
                "code": row["city_code"],
                "name": row["name"],
                "state": row["state"],
                "lat": row["lat"],
                "lon": row["lon"],
                "population": row["population"],
                "zone_count": int(extra.get("zone_count") or 0),
                "service_radius_km": float(extra["service_radius_km"])
                if extra.get("service_radius_km")
                else None,
                "area_km2": float(extra["area_km2"]) if extra.get("area_km2") else None,
                "pipe_length_km": float(extra["pipe_length_km"])
                if extra.get("pipe_length_km")
                else None,
            }
        )
    return out


def read_zone_features(path: str) -> list[dict]:
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
                "city_code": props.get("city_code"),
                "state": props.get("state"),
                "ward": props.get("ward"),
                "centroid_lat": lat,
                "centroid_lon": lon,
                "geojson": feature["geometry"],
                "pipe_length_km": props.get("pipe_length_km"),
                "population": props.get("population"),
                "area_km2": props.get("area_km2"),
            }
        )
    return dedupe_by_id(zones)


def _purge_missing(db, keep_ids: set[str]) -> int:
    """Delete zones not in the incoming file, and everything that references them."""
    stale = [
        zone_id
        for (zone_id,) in db.execute(select(Zone.id)).all()
        if zone_id not in keep_ids
    ]
    if not stale:
        return 0
    for start in range(0, len(stale), CHUNK):
        batch = stale[start : start + CHUNK]
        for model in (ZoneScore, SatelliteSignal, BillingSignal, CitizenReport):
            db.execute(delete(model).where(model.zone_id.in_(batch)))
        db.execute(delete(Zone).where(Zone.id.in_(batch)))
    return len(stale)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="data/india/cities.csv")
    parser.add_argument("--summary", default="data/india/city_summary.csv")
    parser.add_argument("--zones", default="data/india/zones_india.geojson")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="delete zones (and their signals/scores) that are not in --zones",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cities = read_cities(args.cities, args.summary)
    zones = read_zone_features(args.zones)
    if not cities or not zones:
        print("nothing to load", file=sys.stderr)
        return 1

    print(f"parsed {len(cities)} cities and {len(zones):,} zones")
    if args.dry_run:
        for zone in zones[:5]:
            print(f"  {zone['id']}  {zone['name']}  {zone['state']}")
        return 0

    db = SessionLocal()
    try:
        if args.replace:
            removed = _purge_missing(db, {z["id"] for z in zones})
            if removed:
                print(f"--replace: deleted {removed:,} stale zone(s) and their signals")
            db.execute(delete(CityScore))
        upsert(db, City, cities, index_elements=["code"])
        upsert(db, Zone, zones, index_elements=["id"])
        db.commit()
    finally:
        db.close()

    print(f"upserted {len(cities)} cities and {len(zones):,} zones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
