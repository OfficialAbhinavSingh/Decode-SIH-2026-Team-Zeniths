"""Build a zones.geojson for any Indian city from OpenStreetMap boundaries.

Owner: R1 (Satellite & Geo).

    python -m pipelines.satellite.build_city_zones --city Indore \
        --state "Madhya Pradesh" --out ../data/samples/zones.indore.geojson

Then load it exactly like the Jaipur file -- the output schema is identical:

    python -m pipelines.satellite.load_zones ../data/samples/zones.indore.geojson

WHY THIS EXISTS
---------------
data/samples/zones.geojson is a hand-rolled 5x6 grid around Jaipur's centre. It covers
~50 km2 -- about 11% of the Jaipur Municipal Corporation area (~446 km2), and it is not
tied to any real administrative boundary at all. That is fine for a demo and indefensible
as an answer to "which wards are these?".

This script replaces the guesswork with the actual municipal boundary from OpenStreetMap,
then tiles it with the same CELL-degree fishnet seed.py uses, so every downstream
assumption (cell size, naming, zone_id format) is unchanged.

WHAT IT IS NOT
--------------
The cells are still a fishnet, not District Metered Areas. A real DMA is bounded by closed
valves and fed through one metered inflow -- it follows the pipe network, not a lat/lon
grid. These are DMA *proxies*, clipped to a real city boundary. Say that out loud; a judge
from a water utility will ask, and "we clipped a grid to the real JMC boundary" is a much
better answer than "we drew a square".

Grid cells inherit the Modifiable Areal Unit Problem: change --cell and the scores move,
because the boundaries are arbitrary. Swapping in a utility's real DMA boundaries fixes
that, and needs no code change here -- load_zones.py takes any Polygon/MultiPolygon.

NETWORK
-------
Two public, keyless services, both ODbL OpenStreetMap data:
  - Overpass    -- find the boundary relation for the city
  - Nominatim   -- fetch that relation's polygon

Both are rate-limited and neither is a bulk API. Generating one city interactively is
fine; generating hundreds is not -- that needs a Geofabrik India extract processed
offline. Overpass returned HTTP 429 and then refused connections after ~8 city queries
during development, so this script queries once per run and sleeps between retries.

No new dependencies: urllib and json only, matching the rest of the project.
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Same cell size as seed.py's CELL. Keeping these equal means a generated city and the
# seeded Jaipur grid produce comparably-sized zones, so scores stay comparable too.
CELL_DEG = 0.012  # ~1.3 km

# A polite, identifying User-Agent is required by both services' usage policies. Nominatim
# returns 403 to the default Python one.
UA = {"User-Agent": "NeerDrishti-SIH2026/1.0 (github.com/OfficialAbhinavSingh/Decode-SIH-2026-Team-Zeniths)"}

# Several public Overpass instances, tried in order. One endpoint is a single point of
# failure: overpass-api.de rate-limited this script to HTTP 429 and then to refused
# connections during development, and a ban persists for minutes. The mirrors run the
# same software over the same data, so failing over costs nothing but a retry.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
NOMINATIM_LOOKUP = "https://nominatim.openstreetmap.org/lookup"

# Indian admin_level conventions in OSM, best first:
#   8 = municipal corporation / municipality   <- what we want
#   9 = city zone / some corporations are tagged here (Indore is)
#   7 = tehsil / taluk    6 = district         <- far too big, last resort only
PREFERRED_LEVELS = ("8", "9")
FALLBACK_LEVELS = ("7", "6")

# Guardrail. A district boundary at 0.012 deg produces tens of thousands of cells, which
# would silently DoS the loader and the GEE export. Refuse instead.
MAX_ZONES = 2000


# --------------------------------------------------------------------------- geometry


def _ring_points(ring: list) -> list:
    """Drop the repeated closing vertex so it is not counted twice."""
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def exterior_rings(geometry: dict) -> list:
    """Exterior ring(s) of a Polygon or MultiPolygon. Holes are ignored on purpose --
    a city boundary's holes are enclaves we would still want to monitor."""
    kind = geometry.get("type")
    if kind == "Polygon":
        return [geometry["coordinates"][0]]
    if kind == "MultiPolygon":
        return [part[0] for part in geometry["coordinates"]]
    raise ValueError(f"unsupported geometry type {kind!r}")


def bbox(geometry: dict) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for ring in exterior_rings(geometry):
        for lon, lat in _ring_points(ring):
            xs.append(lon)
            ys.append(lat)
    return min(xs), min(ys), max(xs), max(ys)


def point_in_rings(lon: float, lat: float, rings: list) -> bool:
    """Ray casting. Same rule as backend/app/services/geo.py, kept independent so this
    script can run without importing the app (and its database settings)."""
    inside = False
    for ring in rings:
        points = _ring_points(ring)
        count = len(points)
        for i in range(count):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % count]
            if (y1 > lat) != (y2 > lat):
                x_at = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
                if lon < x_at:
                    inside = not inside
    return inside


def square(lon: float, lat: float, half: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - half, lat - half], [lon + half, lat - half],
            [lon + half, lat + half], [lon - half, lat + half],
            [lon - half, lat - half],
        ]],
    }


def fishnet(geometry: dict, cell_deg: float) -> tuple[list, int, int]:
    """Tile the geometry's bbox and keep cells whose centre is inside the boundary.

    Centre-in-polygon, not intersects: a cell straddling the city edge is kept only if
    most of it is inside. That avoids a fringe of near-empty zones whose NDVI mean is
    computed over farmland outside the corporation limit.
    """
    rings = exterior_rings(geometry)
    min_lon, min_lat, max_lon, max_lat = bbox(geometry)
    half = cell_deg / 2.0
    # ceil() on a bare float division is fragile: real coordinates (and even a bbox that
    # "should" divide evenly) pick up ~1e-13 of noise from the floating-point subtraction,
    # which is enough to push ceil() into manufacturing one extra, near-empty row or column
    # of cells along the boundary's edge. A tiny downward nudge before ceiling absorbs that
    # noise without meaningfully changing the grid for any boundary that doesn't.
    epsilon = cell_deg * 1e-9
    cols = max(1, math.ceil((max_lon - min_lon - epsilon) / cell_deg))
    rows = max(1, math.ceil((max_lat - min_lat - epsilon) / cell_deg))
    cells = []
    for row in range(rows):
        for col in range(cols):
            lon = min_lon + (col + 0.5) * cell_deg
            lat = min_lat + (row + 0.5) * cell_deg
            if point_in_rings(lon, lat, rings):
                cells.append((row, col, lat, lon, square(lon, lat, half)))
    return cells, rows, cols


# --------------------------------------------------------------------------- network


def _get(url: str, data: bytes | None = None, timeout: int = 90) -> dict:
    """One request, with a single retry on 429. Both services rate-limit aggressively."""
    for attempt in (1, 2):
        try:
            request = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 1:
                print("  rate-limited, waiting 20s...", file=sys.stderr)
                time.sleep(20)
                continue
            raise
    raise RuntimeError("unreachable")


def find_boundary(city: str, state: str | None, levels: tuple) -> list[dict]:
    """Administrative boundary relations named like `city` at one of `levels`.

    `state` matters more than it looks: there is a Jaipur in Rajasthan and another in
    Purulia district, West Bengal. Without the state filter the generator will happily
    build zones for the wrong city and nothing downstream will notice.
    """
    level_re = "|".join(levels)
    scope = ""
    area = ""
    if state:
        area = f'area["name"="{state}"]["admin_level"="4"]->.s;'
        scope = "(area.s)"
    query = (
        f'[out:json][timeout:60];{area}'
        f'rel["boundary"="administrative"]["admin_level"~"^({level_re})$"]'
        f'["name"~"{city}",i]{scope};out ids tags;'
    )
    last: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            return _get(endpoint, data=query.encode()).get("elements", [])
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            print(f"  {endpoint.split('/')[2]} unavailable ({exc}), trying next mirror",
                  file=sys.stderr)
            last = exc
    raise RuntimeError(f"all Overpass mirrors failed; last error: {last}")


def relation_polygon(relation_id: int) -> tuple[dict | None, str]:
    """Fetch a relation's polygon from Nominatim. Overpass can return the geometry too,
    but reassembling relation members into rings is a lot of code for no benefit."""
    params = urllib.parse.urlencode(
        {"osm_ids": f"R{relation_id}", "format": "json", "polygon_geojson": "1"}
    )
    rows = _get(f"{NOMINATIM_LOOKUP}?{params}", timeout=45)
    if not rows:
        return None, ""
    row = rows[0]
    geometry = row.get("geojson") or {}
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return None, row.get("display_name", "")
    return geometry, row.get("display_name", "")


def pick_boundary(city: str, state: str | None) -> tuple[dict, str, str]:
    """Best available boundary, preferring municipal levels over district ones."""
    for levels, label in ((PREFERRED_LEVELS, "municipal"), (FALLBACK_LEVELS, "FALLBACK")):
        # A failed query is NOT the same as "this city has no municipal boundary", and
        # conflating them is dangerous: during development every Overpass mirror returned
        # 504 for the admin_level 8/9 query, the script treated that as "not found", fell
        # through to admin_level 6, and happily produced 113 zones over Juni Indore Tahsil
        # -- mostly farmland -- when Indore City (admin_level 9) existed the whole time.
        # The only clue was a warning on stderr. Downgrading the boundary because the
        # network blinked is how a demo ends up scoring fields. Abort instead.
        try:
            relations = find_boundary(city, state, levels)
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not silently downgrade
            raise SystemExit(
                f"Overpass lookup failed for admin_level {'/'.join(levels)}: {exc}\n"
                "Refusing to fall back to a coarser boundary on a network error -- that "
                "would silently tile a district instead of a city.\nRetry in a minute; the "
                "public instances rate-limit hard."
            ) from exc
        if not relations:
            continue
        # Prefer an exact name match; OSM often has "Indore City" alongside "Pipliya Indore".
        relations.sort(key=lambda r: (
            r.get("tags", {}).get("name", "").lower() != city.lower(),
            int(r.get("tags", {}).get("admin_level", 99)),
        ))
        for relation in relations[:4]:
            tags = relation.get("tags", {})
            geometry, display = relation_polygon(relation["id"])
            if geometry is None:
                continue
            level = tags.get("admin_level", "?")
            if label == "FALLBACK":
                print(
                    f"  WARNING: no admin_level 8/9 boundary for {city}. Falling back to "
                    f"admin_level {level} ({tags.get('name')}), which is a district or "
                    f"tehsil, NOT the municipal area. Expect farmland in the grid.",
                    file=sys.stderr,
                )
            return geometry, display or tags.get("name", city), level
    raise SystemExit(
        f"no administrative boundary found for {city!r}"
        + (f" in {state!r}" if state else "")
        + ".\nOSM municipal coverage for India is incomplete -- Varanasi and Kochi have no\n"
        "admin_level 8/9 relation at all. Options: pass --state, try the corporation's\n"
        "official name (e.g. 'Greater Chennai Corporation'), or supply a boundary file."
    )


# --------------------------------------------------------------------------- main


def build(city: str, state: str | None, cell: float) -> dict:
    geometry, display, level = pick_boundary(city, state)
    min_lon, min_lat, max_lon, max_lat = bbox(geometry)
    print(f"  boundary: {display} (admin_level {level})")
    print(f"  extent:   ~{(max_lat - min_lat) * 111:.0f} x {(max_lon - min_lon) * 104:.0f} km")

    cells, rows, cols = fishnet(geometry, cell)
    if not cells:
        raise SystemExit(f"boundary produced no cells at --cell {cell}; try a smaller value")
    if len(cells) > MAX_ZONES:
        raise SystemExit(
            f"{len(cells)} cells exceeds MAX_ZONES={MAX_ZONES}. That usually means the "
            f"boundary is a district, not a city. Use a larger --cell or a tighter boundary."
        )
    print(f"  fishnet:  {rows} x {cols} bbox grid -> {len(cells)} cells inside the boundary")

    # `zones.id` is a single global text primary key (docs/DATA-CONTRACT.md) -- it is NOT
    # scoped per city. seed.py's committed Jaipur grid already occupies Z-001..Z-030. A
    # second city generated with the same "Z-{index:03d}" scheme collides on every
    # overlapping id, and load_zones.py's upsert-on-conflict means loading it silently
    # OVERWRITES the first city's zone rows -- name, geometry, everything. Verified this
    # by hand: loading a 70-zone Indore file with plain Z-001..Z-070 ids into a database
    # that already had Jaipur's Z-001..Z-030 left zero Jaipur rows, no error, no warning.
    #
    # Prefixing the id with a code derived from the city name fixes the common case
    # cheaply. It does not fully solve the problem -- two cities whose names produce the
    # same 3-letter code (e.g. "Indore" and "Indraprastha" both -> IND) still collide, and
    # this script cannot know what city codes already exist in the target database. Loading
    # a second city remains something to do deliberately, checking `GET /api/zones?city=`
    # first, not something this script can make fully automatic.
    prefix = "".join(ch for ch in city.upper() if ch.isalnum())[:3] or "ZZZ"

    features = []
    for index, (row, col, lat, lon, polygon) in enumerate(cells, start=1):
        features.append({
            "type": "Feature",
            "geometry": polygon,
            "properties": {
                "zone_id": f"{prefix}-{index:03d}",
                "name": f"Ward {row + 1} - Sector {col + 1}",
                "city": city,
                "ward": f"Ward {row + 1}",
                # Unknown for a generated grid. load_zones.py stores NULL, and nrw.py
                # already treats a missing pipe length as "do not normalise". Inventing a
                # number here would put a fabricated figure in front of a judge.
                "pipe_length_km": None,
                "population": None,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, help="city name as tagged in OSM")
    parser.add_argument("--state", help="disambiguates duplicates; there are two Jaipurs")
    parser.add_argument("--cell", type=float, default=CELL_DEG, help=f"degrees (default {CELL_DEG})")
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    print(f"building zones for {args.city}" + (f", {args.state}" if args.state else ""))
    collection = build(args.city, args.state, args.cell)

    if args.dry_run:
        print(f"  dry run -- would write {len(collection['features'])} zones to {args.out}")
        return 0

    with open(args.out, "w") as handle:
        json.dump(collection, handle)
    print(f"  wrote {len(collection['features'])} zones -> {args.out}")
    print(f"\nnext: python -m pipelines.satellite.load_zones {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
