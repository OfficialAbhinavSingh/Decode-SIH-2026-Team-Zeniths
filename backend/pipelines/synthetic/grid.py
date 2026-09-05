"""Seeded synthetic grid + signal generator. Owner: R1 (Satellite & Geo).

Everything in this module is a pure function: give it a City and it returns plain dicts
shaped like the `zones`, `satellite_signals`, `billing_signals` and `citizen_reports`
rows in docs/DATA-CONTRACT.md. No database, no network, no clock beyond `date.today()`,
which is injectable wherever it matters. That makes the whole generator testable without
standing anything up, and it means `seed_india.py` is a thin writer on top.

THE SEEDING RULE
----------------
Each city draws from its OWN random stream, seeded from its name. Two consequences, both
deliberate:

  * Reproducible. `Jaipur` produces the same 30 zones, the same NDVI anomalies and the
    same NRW figures on every machine and every run, so the demo never changes under you
    and a screenshot taken today still matches the map next week.

  * Independent. Adding Kohima to the registry, or reordering CITIES, cannot shift a
    single number in Pune. seed.py's own comments flag this hazard -- it shares one
    `Random(2026)` across all its work, so skipping a signal there silently moves every
    later draw. Per-city streams remove the hazard rather than documenting it.

`hash()` is NOT usable for this: Python randomises str hashing per process (PYTHONHASHSEED),
so it would give a city a different grid on every run. SHA-256 of the name is stable
across processes, machines and Python versions.

WHAT THIS DATA IS
-----------------
Synthetic. Every NDVI anomaly, NRW percentage and citizen report below is generated, not
observed. The bands they are drawn from are chosen to look like published Indian urban
water figures (NRW is commonly quoted at 30-40%), but no row here is evidence of anything
in the real world. `BillingSignal.is_synthetic` is set True for exactly this reason, and
satellite rows are written with source="seed" so fusion's `_REAL_SATELLITE_FIRST` ordering
lets a genuine Sentinel-2 ingest win over them without a code change.
"""

import hashlib
import math
import random
from datetime import date, datetime, timedelta, timezone

from .cities import City

# Same cell size as seed.py's CELL and build_city_zones.py's CELL_DEG. Keeping all three
# equal is what makes zones comparable between a seeded city, a synthetic one and a real
# OSM-clipped one -- change it in one place and scores stop meaning the same thing.
CELL = 0.012  # ~1.3 km per zone side

# Roughly how many zones carry a planted leak. Held at seed.py's ratio (1 in 8, floor 3)
# so a synthetic city has the same signal-to-noise as the Jaipur grid the demo was tuned on.
HOTSPOT_RATIO = 8
MIN_HOTSPOTS = 3

REPORT_TEXTS = (
    "Water flowing on the road since morning",
    "Road is always wet near the corner, no rain here",
    "Low pressure for a week and water on the street",
    "Pipeline leaking beside the school gate",
)


def city_seed(name: str) -> int:
    """A stable 64-bit seed for a city name.

    Stable is the whole requirement: the same name must give the same number in every
    process, so this cannot use hash(), which Python salts per interpreter.
    """
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(city: City) -> random.Random:
    return random.Random(city_seed(city.name))


def grid_cols(count: int) -> int:
    """Columns for a `count`-cell grid, slightly wider than tall.

    The 1.2 is not decoration. seed.py hardcodes cols=6 for its 30-zone Jaipur grid, and
    Jaipur's zone ids are what the live dashboard has always shown; ceil(sqrt(30 * 1.2))
    is exactly 6, so the pinned city falls out of the general formula unchanged instead of
    needing a special case here.
    """
    return max(1, math.ceil(math.sqrt(count * 1.2)))


def make_polygon(lat: float, lon: float, cell: float = CELL) -> dict:
    half = cell / 2
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def billing_period(today: date | None = None) -> tuple[date, date]:
    """The last full calendar month -- the same window seed.py and R2's generator use.

    BillingSignal's natural key is (zone_id, period_start, period_end), so this MUST match
    backend/seed.py and backend/pipelines/billing/generate.py. When it matches, R2's real
    pipeline upserts *over* a synthetic row for the same zone and month; when it drifts,
    both rows survive and fusion's "latest period_end" lookup can keep picking the fake
    one forever. tests/test_synthetic_grid.py asserts they agree.
    """
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def build_zones(city: City, rng: random.Random | None = None) -> list[dict]:
    """The grid itself: `city.zone_count` square cells centred on the city.

    Returns dicts with exactly the columns of the `zones` table. Identical in shape to
    seed.py's build_zones() -- same id scheme, same "Ward N - Sector M" naming, same cell
    geometry -- which is what "recreate the Jaipur format for all of India" means here.
    """
    rng = rng or rng_for(city)
    count = city.zone_count
    cols = grid_cols(count)
    rows = []
    for i in range(count):
        row, col = divmod(i, cols)
        lat = city.lat + (row - count / cols / 2) * CELL
        lon = city.lon + (col - cols / 2) * CELL
        rows.append(
            {
                # Prefixed by the registry's per-city code. A bare Z-001..Z-0NN scheme
                # collides across cities and the loader's upsert silently overwrites the
                # first city's rows -- the bug fixed in 656781c. cities.py guarantees the
                # prefixes are unique; a test enforces it.
                "id": f"{city.code}-{i + 1:03d}",
                "name": f"Ward {row + 1} - Sector {col + 1}",
                "city": city.name,
                "ward": f"Ward {row + 1}",
                "centroid_lat": round(lat, 6),
                "centroid_lon": round(lon, 6),
                "geojson": make_polygon(lat, lon),
                "pipe_length_km": round(rng.uniform(3.0, 14.0), 2),
                "population": rng.randint(4_000, 22_000),
            }
        )
    return rows


def pick_hotspots(zones: list[dict], rng: random.Random) -> set[str]:
    """Which zones carry a planted leak. Same 1-in-8 rule as seed.py."""
    k = max(MIN_HOTSPOTS, len(zones) // HOTSPOT_RATIO)
    return {z["id"] for z in rng.sample(zones, k=min(k, len(zones)))}


def build_signals(
    city: City,
    zones: list[dict],
    rng: random.Random,
    today: date | None = None,
    now: datetime | None = None,
) -> dict[str, list[dict]]:
    """Three signals over an already-built grid, as plain dicts.

    Returns {"satellite": [...], "billing": [...], "citizen": [...]}.
    """
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    observed = today - timedelta(days=3)
    period_start, period_end = billing_period(today)
    hotspots = pick_hotspots(zones, rng)

    # A per-city baseline, so the country does not come out looking uniformly average.
    # Cities genuinely differ in how leaky their networks are, and a map where every one
    # sits at the same NRW is both less useful and less believable than one where they do
    # not. Still synthetic -- a plausible spread, not a measured one.
    nrw_floor = rng.uniform(10.0, 24.0)
    nrw_spread = rng.uniform(12.0, 22.0)

    satellite: list[dict] = []
    billing: list[dict] = []
    citizen: list[dict] = []

    for zone in zones:
        hot = zone["id"] in hotspots

        # --- satellite: NDVI above a 3-year baseline over the pipe corridor. A leak keeps
        # the strip above the main greener than its own history, which is the signal.
        baseline = round(rng.uniform(0.24, 0.38), 3)
        anomaly = round(rng.uniform(0.10, 0.22) if hot else rng.gauss(0.01, 0.035), 3)
        satellite.append(
            {
                "zone_id": zone["id"],
                "observed_on": observed,
                "ndvi_mean": round(baseline + anomaly, 3),
                "ndvi_baseline": baseline,
                "ndvi_anomaly": anomaly,
                "wetness_index": round(rng.uniform(0.1, 0.6), 3),
                "cloud_pct": round(rng.uniform(0, 15), 1),
                "score": max(0.0, min(100.0, round(anomaly / 0.22 * 100, 2))),
                # Real Sentinel-2 rows carry source="sentinel2-gee". Keeping "seed" here is
                # what lets fusion prefer genuine data over this the moment any arrives.
                "source": "seed",
            }
        )

        # --- billing: non-revenue water for the month.
        if hot:
            nrw = nrw_floor + nrw_spread + rng.uniform(8, 20)
        else:
            nrw = nrw_floor + rng.uniform(0, nrw_spread)
        nrw = max(2.0, min(72.0, nrw))
        supplied = round(rng.uniform(9_000, 40_000), 1)
        billing.append(
            {
                "zone_id": zone["id"],
                "period_start": period_start,
                "period_end": period_end,
                "supplied_kl": supplied,
                "billed_kl": round(supplied * (1 - nrw / 100), 1),
                "nrw_pct": round(nrw, 2),
                # 0% NRW -> 0, 60%+ NRW -> 100
                "score": round(max(0.0, min(100.0, nrw / 60 * 100)), 2),
                "is_synthetic": True,
            }
        )

        # --- citizen: hotspots get several reports, most zones get none. Reports scatter
        # inside the cell rather than pinning to its centroid, because R5's zone matcher is
        # a point-in-polygon test and a centroid would never exercise it.
        report_count = rng.randint(2, 6) if hot else rng.choices([0, 1], [0.8, 0.2])[0]
        for n in range(report_count):
            citizen.append(
                {
                    "zone_id": zone["id"],
                    "reported_at": now - timedelta(days=rng.randint(0, 25), hours=n),
                    "channel": rng.choice(["whatsapp", "web"]),
                    "reporter_hash": f"sha256:synth{rng.randint(10**6, 10**7)}",
                    "description": rng.choice(REPORT_TEXTS),
                    "lat": zone["centroid_lat"] + rng.uniform(-CELL / 3, CELL / 3),
                    "lon": zone["centroid_lon"] + rng.uniform(-CELL / 3, CELL / 3),
                    "status": "new",
                }
            )

    return {"satellite": satellite, "billing": billing, "citizen": citizen}


def build_city(
    city: City, today: date | None = None, now: datetime | None = None
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Everything for one city: (zone rows, signal rows). Deterministic in `city.name`."""
    rng = rng_for(city)
    zones = build_zones(city, rng)
    return zones, build_signals(city, zones, rng, today=today, now=now)
