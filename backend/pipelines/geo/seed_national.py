"""Seed satellite and citizen signals for the whole national zone set.

Owner: R2 (Data).

WHAT THIS IS: the national equivalent of `backend/seed.py` -- it exists so the pan-India
map is alive before Google Earth Engine has exported NDVI for seven thousand polygons, and
so the offline demo fallback (SCOPE.md M8) has something to draw. Every row it writes is
stamped `source="seed"` and every billing row stays `is_synthetic=true`. Nothing here is
presented as a measurement.

WHAT IT IS NOT: a shortcut around the real pipelines. Two of the three lanes stay real:

  - Billing comes from `pipelines/billing/generate.py` + `load.py`, the benchmarked
    generator with its CPHEEO/AMRUT citations. This module does not touch it.
  - NDVI *scoring* runs through `pipelines/satellite/ndvi.score_batch()` -- the same
    city-relative-anomaly code the GEE export feeds -- so the anomaly maths, the rain
    median subtraction and the saturation curve are all exercised for real. Only the raw
    ndvi_mean/ndvi_baseline numbers are fabricated, and swapping a GEE export in replaces
    exactly those two columns.

The point of the distinction: when a judge asks "is this a real leak or a demo?", the
answer is a precise one -- the geography, the groundwater, the rainfall and the scoring
are real; the NDVI pixels and the citizen reports are seeded until a city gives us access.

    python -m pipelines.geo.seed_national --hotspot-rate 0.08
    python -m pipelines.geo.seed_national --city-code JAI    # one city only
"""

import argparse
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import CitizenReport, SatelliteSignal, Zone
from app.upsert import upsert

from ..satellite.ndvi import score_batch

# Fixed seed: everyone on the team sees the same national map, and the demo is
# reproducible on stage. Same rule as backend/seed.py.
RNG = random.Random(2026)

DESCRIPTIONS = [
    "Water flowing on the road since morning",
    "Road is always wet near the corner, no rain here",
    "Low pressure for a week and water on the street",
    "Pipeline leaking beside the school gate",
    "Water standing in the lane for four days",
]


def build_signals(zones: list[Zone], hotspot_rate: float, observed: date) -> list[dict]:
    """Fabricate NDVI readings, then score them with the real pipeline.

    Scoring is per city, because `ndvi.city_relative_anomaly()` subtracts the city-wide
    median -- pooling the whole country into one batch would compare Kochi's monsoon
    greenness against Jodhpur's desert and call half of Kerala a leak.
    """
    by_city: dict[str, list[Zone]] = {}
    for zone in zones:
        by_city.setdefault(zone.city_code or zone.city, []).append(zone)

    out: list[dict] = []
    for city_zones in by_city.values():
        count = max(1, round(len(city_zones) * hotspot_rate))
        hotspots = {z.id for z in RNG.sample(city_zones, k=min(count, len(city_zones)))}

        rows = []
        for zone in city_zones:
            hot = zone.id in hotspots
            baseline = round(RNG.uniform(0.24, 0.38), 3)
            anomaly = round(RNG.uniform(0.10, 0.22) if hot else RNG.gauss(0.01, 0.035), 3)
            rows.append(
                {
                    "zone_id": zone.id,
                    "observed_on": observed,
                    "ndvi_mean": round(baseline + anomaly, 3),
                    "ndvi_baseline": baseline,
                    "wetness_index": round(RNG.uniform(0.1, 0.6), 3),
                    "cloud_pct": round(RNG.uniform(0, 15), 1),
                    "source": "seed",
                    "_hot": hot,
                }
            )
        score_batch(rows)  # adds ndvi_anomaly + score, the real scoring path
        out.extend(rows)
    return out


def build_reports(zones: list[Zone], hot_ids: set[str], now: datetime) -> list[CitizenReport]:
    reports = []
    for zone in zones:
        hot = zone.id in hot_ids
        count = RNG.randint(2, 6) if hot else RNG.choices([0, 1], [0.85, 0.15])[0]
        for n in range(count):
            jitter = 0.004
            reports.append(
                CitizenReport(
                    zone_id=zone.id,
                    reported_at=now - timedelta(days=RNG.randint(0, 25), hours=n),
                    channel=RNG.choice(["whatsapp", "web"]),
                    reporter_hash=f"sha256:seed{RNG.randint(10**6, 10**7)}",
                    description=RNG.choice(DESCRIPTIONS),
                    lat=zone.centroid_lat + RNG.uniform(-jitter, jitter),
                    lon=zone.centroid_lon + RNG.uniform(-jitter, jitter),
                    status="new",
                )
            )
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city-code", default=None, help="seed one city instead of all")
    parser.add_argument("--hotspot-rate", type=float, default=0.08)
    parser.add_argument("--days-ago", type=int, default=3, help="observation date offset")
    parser.add_argument("--skip-reports", action="store_true")
    args = parser.parse_args()

    observed = date.today() - timedelta(days=args.days_ago)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        stmt = select(Zone)
        if args.city_code:
            stmt = stmt.where(Zone.city_code == args.city_code)
        zones = list(db.scalars(stmt).all())
        if not zones:
            print("no zones -- run pipelines.geo.load_national first")
            return 1

        rows = build_signals(zones, args.hotspot_rate, observed)
        hot_ids = {r["zone_id"] for r in rows if r.pop("_hot", False)}
        upsert(db, SatelliteSignal, rows, index_elements=["zone_id", "observed_on"])

        if not args.skip_reports:
            zone_ids = [z.id for z in zones]
            for start in range(0, len(zone_ids), 500):
                db.execute(
                    delete(CitizenReport).where(CitizenReport.zone_id.in_(zone_ids[start : start + 500]))
                )
            db.add_all(build_reports(zones, hot_ids, now))

        db.commit()
    finally:
        db.close()

    cities = {r["zone_id"].rsplit("-", 1)[0] for r in rows}
    print(f"seeded {len(rows):,} satellite readings across {len(cities)} cities")
    print(f"planted {len(hot_ids):,} leak hotspots (source='seed', not a measurement)")
    print("next: python -m pipelines.billing.generate ... && POST /api/fusion/run/national")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
