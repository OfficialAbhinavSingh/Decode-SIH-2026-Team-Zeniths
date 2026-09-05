"""Fetch and simplify India's state/UT boundaries for the national choropleth.

Owner: R2 (Data). One-off-feeling but scripted, not hand-edited -- if the source repo
tags a new revision, re-running this reproduces `data/india/states.geojson` exactly.

SOURCE: datta07/INDIAN-SHAPEFILES, `INDIA/INDIA_STATES.geojson` (37 states/UTs, Census
2011 boundaries). https://github.com/datta07/INDIAN-SHAPEFILES

WHY SIMPLIFY: the raw file is 2.2 MB of coastline detail nobody needs at country zoom --
a state polygon on the national map is a handful of pixels, and Rameswaram's coastline at
full resolution costs bytes for a colour fill that reads the same in an outline. Simplified
with Shapely's Douglas-Peucker at tolerance 0.01 degrees (roughly 1 km), which keeps every
state recognisable and the visual island chains intact, and cuts the file below 1 MB.

WHY MERGE Dadra & Nagar Haveli with Daman & Diu: the two Union Territories merged into one
administrative unit in January 2020. The source shapefile still carries the pre-merger
boundary, and CGWB's 2023 groundwater table already reports them as the merged unit -- the
merge here keeps the boundary file and the groundwater join on the same side of that
change, so `Zone.state` matches `GroundwaterStress.state` for every zone in the UT.

    python -m pipelines.geo.fetch_state_boundaries --out ../data/india/states.geojson
"""

import argparse
import sys

SOURCE_URL = (
    "https://raw.githubusercontent.com/datta07/INDIAN-SHAPEFILES/master/"
    "INDIA/INDIA_STATES.geojson"
)

# Raw shapefile spelling -> the name used everywhere else in this codebase (GeoNames'
# admin1 spelling, which `pipelines.geo.registry` and the CGWB CSV both already use).
NAME_MAP = {
    "ANDAMAN & NICOBAR": "Andaman and Nicobar",
    "ANDHRA PRADESH": "Andhra Pradesh",
    "ARUNACHAL PRADESH": "Arunachal Pradesh",
    "ASSAM": "Assam",
    "BIHAR": "Bihar",
    "CHANDIGARH": "Chandigarh",
    "CHHATTISGARH": "Chhattisgarh",
    "DADRA & NAGAR HAVELI": "Dadra and Nagar Haveli and Daman and Diu",
    "DAMAN & DIU": "Dadra and Nagar Haveli and Daman and Diu",
    "DELHI": "Delhi",
    "GOA": "Goa",
    "GUJARAT": "Gujarat",
    "HARYANA": "Haryana",
    "HIMACHAL PRADESH": "Himachal Pradesh",
    "JAMMU & KASHMIR": "Jammu and Kashmir",
    "JHARKHAND": "Jharkhand",
    "KARNATAKA": "Karnataka",
    "KERALA": "Kerala",
    "LADAKH": "Ladakh",
    "LAKSHADWEEP": "Lakshadweep",
    "MADHYA PRADESH": "Madhya Pradesh",
    "MAHARASHTRA": "Maharashtra",
    "MANIPUR": "Manipur",
    "MEGHALAYA": "Meghalaya",
    "MIZORAM": "Mizoram",
    "NAGALAND": "Nagaland",
    "ODISHA": "Odisha",
    "PUDUCHERRY": "Puducherry",
    "PUNJAB": "Punjab",
    "RAJASTHAN": "Rajasthan",
    "SIKKIM": "Sikkim",
    "TAMIL NADU": "Tamil Nadu",
    "TELANGANA": "Telangana",
    "TRIPURA": "Tripura",
    "UTTAR PRADESH": "Uttar Pradesh",
    "UTTARAKHAND": "Uttarakhand",
    "WEST BENGAL": "West Bengal",
}

SIMPLIFY_TOLERANCE_DEG = 0.01


def build(raw: dict) -> dict:
    from shapely.geometry import mapping, shape

    merged: dict[str, object] = {}
    unmapped = set()
    for feature in raw["features"]:
        raw_name = feature["properties"].get("STNAME", "").strip()
        state = NAME_MAP.get(raw_name)
        if not state:
            unmapped.add(raw_name)
            continue
        geom = shape(feature["geometry"]).simplify(
            SIMPLIFY_TOLERANCE_DEG, preserve_topology=True
        )
        merged[state] = geom.union(merged[state]) if state in merged else geom

    if unmapped:
        print(f"warning: unmapped state name(s), skipped: {sorted(unmapped)}", file=sys.stderr)

    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": mapping(geom), "properties": {"state": state}}
            for state, geom in merged.items()
        ],
    }


def main() -> int:
    import json

    import httpx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/india/states.geojson")
    parser.add_argument("--source", default=SOURCE_URL)
    args = parser.parse_args()

    response = httpx.get(args.source, timeout=60, follow_redirects=True)
    response.raise_for_status()
    fc = build(response.json())

    with open(args.out, "w") as fh:
        json.dump(fc, fh, separators=(",", ":"))

    import os

    print(f"wrote {len(fc['features'])} states/UTs, {os.path.getsize(args.out) / 1e6:.2f} MB -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
