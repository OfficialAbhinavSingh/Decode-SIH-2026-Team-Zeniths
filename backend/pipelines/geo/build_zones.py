"""Build the national zone layer from the city registry.

Owner: R2 (Data).

    # 1. registry (once)
    python -m pipelines.geo.registry --out ../data/india/cities.csv
    # 2. zones for every city in it
    python -m pipelines.geo.build_zones --cities ../data/india/cities.csv \
        --out ../data/india/zones_india.geojson
    # a smaller demo set -- the 40 largest cities only
    python -m pipelines.geo.build_zones --top 40 --out ../data/india/zones_demo.geojson

Deterministic: same registry in, byte-identical GeoJSON out. No RNG anywhere in this
lane, so a national rebuild during the demo cannot change what the judges already saw.

Neighbour de-confliction: cities within `--neighbour-radius` km of each other compete for
cells, and the nearest city wins. That is what stops Delhi/Noida/Ghaziabad and
Mumbai/Thane/Navi Mumbai from triple-counting the same neighbourhoods.
"""

import argparse
import json
import os
import sys
from collections import Counter

from .registry import read_csv
from .tessellate import neighbours_within, service_radius_km, tessellate

# How far to look for a competing city. Two cities further apart than this cannot have
# overlapping service discs at any Indian population, so the test would be wasted work.
DEFAULT_NEIGHBOUR_RADIUS_KM = 60.0


def build(
    cities: list[dict],
    neighbour_radius_km: float = DEFAULT_NEIGHBOUR_RADIUS_KM,
    max_zones_per_city: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (zone features, per-city summary rows)."""
    features: list[dict] = []
    summary: list[dict] = []

    for city in cities:
        nearby = neighbours_within(city, cities, neighbour_radius_km)
        zones = tessellate(city, neighbours=nearby, max_zones=max_zones_per_city)
        features.extend(zones)
        summary.append(
            {
                "city_code": city["city_code"],
                "name": city["name"],
                "state": city["state"],
                "lat": city["lat"],
                "lon": city["lon"],
                "population": city["population"],
                "zone_count": len(zones),
                "service_radius_km": round(service_radius_km(int(city["population"])), 3),
                "modelled_population": sum(z["properties"]["population"] for z in zones),
                "retention": zones[0]["properties"]["retention"] if zones else 1.0,
                "area_km2": round(sum(z["properties"]["area_km2"] for z in zones), 2),
                "pipe_length_km": round(
                    sum(z["properties"]["pipe_length_km"] for z in zones), 2
                ),
            }
        )
    return features, summary


def write_geojson(features: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, separators=(",", ":"))


def write_summary(summary: list[dict], path: str) -> None:
    import csv

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="data/india/cities.csv")
    parser.add_argument("--out", default="data/india/zones_india.geojson")
    parser.add_argument("--summary-out", default="data/india/city_summary.csv")
    parser.add_argument("--top", type=int, default=None, help="only the N largest cities")
    parser.add_argument("--state", default=None, help="restrict to one state")
    parser.add_argument("--max-zones", type=int, default=None, help="cap zones per city")
    parser.add_argument(
        "--neighbour-radius", type=float, default=DEFAULT_NEIGHBOUR_RADIUS_KM
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cities = read_csv(args.cities)
    if args.state:
        cities = [c for c in cities if c["state"].casefold() == args.state.casefold()]
    if args.top:
        cities = cities[: args.top]
    if not cities:
        print("no cities selected", file=sys.stderr)
        return 1

    features, summary = build(cities, args.neighbour_radius, args.max_zones)

    ids = Counter(f["properties"]["zone_id"] for f in features)
    duplicates = [zone_id for zone_id, n in ids.items() if n > 1]
    if duplicates:
        # zone_id is the join key for every signal table; a duplicate would silently fuse
        # two zones' water. Refuse to write a file that would do that.
        print(f"FATAL: {len(duplicates)} duplicate zone_id(s), e.g. {duplicates[:5]}", file=sys.stderr)
        return 1

    states = {c["state"] for c in cities}
    print(f"{len(features):,} zones · {len(cities)} cities · {len(states)} states/UTs")
    print(f"modelled population {sum(s['modelled_population'] for s in summary) / 1e6:.1f} M")
    print(f"modelled mains {sum(s['pipe_length_km'] for s in summary):,.0f} km")
    print(f"modelled service area {sum(s['area_km2'] for s in summary):,.0f} km2")
    clipped = [s for s in summary if s["retention"] < 0.95]
    print(f"{len(clipped)} cities clipped by a neighbour (population scaled to the area kept)")
    print("largest:")
    for row in summary[:6]:
        print(f"  {row['city_code']}  {row['name']:<16} {row['zone_count']:>3} zones  r={row['service_radius_km']:.1f} km")

    if args.dry_run:
        return 0
    write_geojson(features, args.out)
    write_summary(summary, args.summary_out)
    print(f"wrote {args.out} and {args.summary_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
