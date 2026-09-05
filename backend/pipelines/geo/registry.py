"""Build the pan-India city registry -- the spine of national coverage.

Owner: R2 (Data). Extends the single-city MVP to every Class-I urban centre in India.

WHY GEONAMES: we need, for ~500 Indian cities, three things that must be *real* and not
invented -- the city's name, its coordinates, and its population. Census 2011's town
directory has all three but ships as scanned PDFs and per-state XLS files; parsing 36 of
those inside a hackathon is how you lose a week. GeoNames publishes the same populated
places as one tab-separated dump, refreshed daily, CC-BY 4.0, no key, no quota. Its
Indian population figures are Census-2011-derived for exactly the towns we care about.

SOURCES:
  1. GeoNames geographical database -- India dump (`IN.zip`), CC BY 4.0.
     Columns used: name, latitude, longitude, feature class/code, admin1, population.
     https://download.geonames.org/export/dump/IN.zip
     Licence: https://creativecommons.org/licenses/by/4.0/

  2. GeoNames admin1 code table, for the state name behind each `IN.NN` code.
     https://download.geonames.org/export/dump/admin1CodesASCII.txt

  3. Census of India 2011, Primary Census Abstract -- the definition we filter on.
     A "Class-I city" is an urban centre with population >= 100,000; there were 468 of
     them in 2011. Filtering GeoNames at the same threshold reproduces that universe
     (we get a few more, because GeoNames carries post-2011 municipal growth).
     https://censusindia.gov.in/census.website/data/census-tables

DEDUPLICATION -- THE ONE THING YOU MUST GET RIGHT: GeoNames does not distinguish a
municipal corporation from a neighbourhood inside one. `Karol Bagh` (505k) and `Dharavi`
(700k) are listed beside `Delhi` (11.0M) and `Mumbai` (12.7M) as if they were peer cities.
Left alone that is a double-count -- Dharavi's residents are already inside Mumbai's 12.7M
-- and it also lets a neighbourhood win the nearest-city test against its own parent,
which is why an unfiltered build gives Delhi three zones and Bengaluru twenty-nine.
`absorb_suburbs()` folds a place into a larger one when it sits inside that city's service
footprint *and* has under a tenth of its population, which separates `Dharavi` (absorbed)
from `Navi Mumbai` and `Thane` (kept -- they are their own corporations with their own
water supply). See ABSORB_POPULATION_RATIO for the threshold and why.

WHAT THIS IS NOT: GeoNames gives us a *point*, not a municipal boundary. Real ULB
polygons for all of India are not openly published as one file. `tessellate.py` turns the
point plus the population into a defensible service-area footprint, and documents that
approximation rather than hiding it. A city that later hands us its real ward shapefile
drops straight in -- `load_zones.py` already reads any GeoJSON.

    python -m pipelines.geo.registry --out ../data/india/cities.csv
    python -m pipelines.geo.registry --min-population 250000 --limit 100
"""

import argparse
import csv
import io
import os
import sys
import unicodedata
import zipfile

GEONAMES_DUMP = "https://download.geonames.org/export/dump/IN.zip"
GEONAMES_ADMIN1 = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"

# Census 2011 Class-I threshold. Below this a place is a Class-II town or smaller and
# almost never has a metered piped network worth running NRW analysis on.
CLASS_I_POPULATION = 100_000

# GeoNames feature codes for "a place people live in", ordered most to least
# municipal. PPLA* are administrative seats (state/district capitals), PPL is a generic
# populated place, PPLC is the national capital.
POPULATED_PLACE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLX"}

# The dump's tab-separated column order (see the readme.txt inside IN.zip).
COL_NAME = 1
COL_LAT = 4
COL_LON = 5
COL_FEATURE_CLASS = 6
COL_FEATURE_CODE = 7
COL_ADMIN1 = 10
COL_ADMIN2 = 11
COL_POPULATION = 14


# A place inside a larger city's service radius holding less than this fraction of its
# population is a neighbourhood of it, not a peer utility. Calibrated on the cases that
# matter: Dharavi is 5.5% of Mumbai and gets absorbed; Navi Mumbai is 20.5% and is kept,
# because NMMC really does run its own water supply. Anything between is a judgement call
# and this is where to change it.
ABSORB_POPULATION_RATIO = 0.10


def absorb_suburbs(cities: list[dict]) -> tuple[list[dict], list[dict]]:
    """Fold neighbourhood-scale entries into the city that contains them.

    Returns (kept, absorbed). `kept` rows gain an `absorbed_places` count so the national
    totals can be defended: "Mumbai is one row, not seven, and here is what we merged."

    Input must be sorted largest-population-first, so a city is only ever absorbed into
    one already-accepted, strictly larger city.
    """
    from .tessellate import haversine_km, service_radius_km

    kept: list[dict] = []
    absorbed: list[dict] = []
    for city in cities:
        parent = None
        for candidate in kept:
            if city["population"] >= candidate["population"] * ABSORB_POPULATION_RATIO:
                continue
            distance = haversine_km(
                city["lat"], city["lon"], candidate["lat"], candidate["lon"]
            )
            if distance <= service_radius_km(candidate["population"]):
                parent = candidate
                break
        if parent is None:
            city["absorbed_places"] = 0
            kept.append(city)
        else:
            parent["absorbed_places"] = parent.get("absorbed_places", 0) + 1
            absorbed.append({**city, "absorbed_into": parent["name"]})
    return kept, absorbed


def city_code(name: str, taken: set[str]) -> str:
    """A short, stable, human-readable prefix for this city's zone IDs.

    `Jaipur` -> `JAI`, so its zones read `JAI-001` instead of an opaque `Z-4417`. A code
    that collides (Kanpur and Kannur both want `KAN`) grows a digit rather than silently
    stealing the other city's zones -- zone_id is the join key for every signal table, so
    a collision here would fuse two cities' water into one score.
    """
    # Fold diacritics before taking letters: GeoNames spells the city `Thāne`, and a
    # zone id of `THĀ-012` has to survive a URL path, a CSV opened in Excel and a GEE
    # export filename. The display name keeps its diacritics; only the code is folded.
    folded = unicodedata.normalize("NFKD", name)
    letters = "".join(
        ch for ch in folded.upper() if ch.isalpha() and ch.isascii()
    )
    base = (letters[:3] or "IND").ljust(3, "X")
    if base not in taken:
        taken.add(base)
        return base
    for suffix in range(2, 100):
        candidate = f"{base}{suffix}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    raise ValueError(f"could not allocate a unique city code for {name!r}")


def read_admin1(text: str) -> dict[str, str]:
    """`IN.24` -> `Rajasthan`. The file is global; we keep only the Indian rows."""
    states: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].startswith("IN."):
            states[parts[0].split(".", 1)[1]] = parts[1]
    return states


def parse_dump(
    lines,
    states: dict[str, str],
    min_population: int = CLASS_I_POPULATION,
) -> list[dict]:
    """Filter the GeoNames dump down to Indian cities worth modelling.

    Deduplicates on (name, state): GeoNames often carries a city twice -- once as the
    municipality and once as its administrative seat -- and the higher-population row is
    the municipal one. Keeping both would double-count a city in every national total.
    """
    best: dict[tuple[str, str], dict] = {}
    for line in lines:
        parts = line.rstrip("\n").split("\t")
        if len(parts) <= COL_POPULATION:
            continue
        if parts[COL_FEATURE_CLASS] != "P":
            continue
        if parts[COL_FEATURE_CODE] not in POPULATED_PLACE_CODES:
            continue
        try:
            population = int(parts[COL_POPULATION] or 0)
        except ValueError:
            continue
        if population < min_population:
            continue

        state = states.get(parts[COL_ADMIN1], "")
        if not state:
            # An unmapped admin1 means we cannot say which state's water board owns it,
            # and the national rollup is by state. Drop it rather than file it under "".
            continue

        name = parts[COL_NAME].strip()
        key = (name.casefold(), state.casefold())
        row = {
            "name": name,
            "state": state,
            "district_code": parts[COL_ADMIN2] or "",
            "lat": round(float(parts[COL_LAT]), 6),
            "lon": round(float(parts[COL_LON]), 6),
            "population": population,
            "feature_code": parts[COL_FEATURE_CODE],
        }
        if key not in best or population > best[key]["population"]:
            best[key] = row

    cities = sorted(best.values(), key=lambda c: (-c["population"], c["name"]))
    cities, _absorbed = absorb_suburbs(cities)
    taken: set[str] = set()
    for city in cities:
        city["city_code"] = city_code(city["name"], taken)
    return cities


def fetch(url: str, timeout: float = 120.0) -> bytes:
    import httpx

    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.content


def build(min_population: int, limit: int | None, cache_dir: str | None) -> list[dict]:
    """Download (or reuse a cached copy of) the dumps and produce the registry rows."""
    dump_bytes = _cached(cache_dir, "IN.zip", GEONAMES_DUMP)
    admin1_bytes = _cached(cache_dir, "admin1CodesASCII.txt", GEONAMES_ADMIN1)

    states = read_admin1(admin1_bytes.decode("utf-8"))
    with zipfile.ZipFile(io.BytesIO(dump_bytes)) as archive:
        with archive.open("IN.txt") as fh:
            text = io.TextIOWrapper(fh, encoding="utf-8")
            cities = parse_dump(text, states, min_population)

    return cities[:limit] if limit else cities


def _cached(cache_dir: str | None, filename: str, url: str) -> bytes:
    """Fetch once, reuse after. The India dump is 16 MB -- re-downloading it on every
    tweak of the population threshold wastes a minute each time and is rude to GeoNames.
    """
    if not cache_dir:
        return fetch(url)
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, filename)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as fh:
            return fh.read()
    payload = fetch(url)
    with open(path, "wb") as fh:
        fh.write(payload)
    return payload


FIELDS = [
    "city_code",
    "name",
    "state",
    "district_code",
    "lat",
    "lon",
    "population",
    "feature_code",
    "absorbed_places",
]


def write_csv(cities: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(cities)


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    **raw,
                    "lat": float(raw["lat"]),
                    "lon": float(raw["lon"]),
                    "population": int(raw["population"]),
                    "absorbed_places": int(raw.get("absorbed_places") or 0),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/india/cities.csv")
    parser.add_argument("--min-population", type=int, default=CLASS_I_POPULATION)
    parser.add_argument("--limit", type=int, default=None, help="keep only the N largest")
    parser.add_argument("--cache-dir", default=".cache/geonames")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cities = build(args.min_population, args.limit, args.cache_dir)
    if not cities:
        print("no cities matched -- is the population threshold too high?", file=sys.stderr)
        return 1

    states = {c["state"] for c in cities}
    total = sum(c["population"] for c in cities)
    print(f"{len(cities)} cities across {len(states)} states/UTs, {total / 1e6:.1f} M people")
    for city in cities[:8]:
        print(f"  {city['city_code']}  {city['name']:<18} {city['state']:<20} {city['population']:>10,}")

    if args.dry_run:
        return 0
    write_csv(cities, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
