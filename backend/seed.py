"""Seed the database with a realistic fake city so every lane can work in parallel.

This is the reason nobody is blocked on day 1: run it and the API returns full,
plausible data for all three signals plus fusion scores, before a single real
pipeline exists. Re-run any time to reset -- it wipes and rebuilds.

    python seed.py            # default city from .env
    python seed.py --city Jaipur --zones 30

Real pipelines (R1 satellite, R2 billing, R5 citizen) replace this data by POSTing to
the ingest endpoints. They do not need to change this file.
"""

import argparse
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import BillingSignal, CitizenReport, SatelliteSignal, Zone, ZoneScore
from app.services.fusion import run_fusion

# Fixed seed: everyone on the team sees the same map, and the demo is reproducible.
RNG = random.Random(2026)

CITY_CENTRES = {
    "Jaipur": (26.9124, 75.7873),
    "Pune": (18.5204, 73.8567),
    "Indore": (22.7196, 75.8577),
}

CELL = 0.012  # ~1.3 km per zone side


def billing_period(today: date | None = None) -> tuple[date, date]:
    """The billing period seeded rows use: the last full calendar month.

    This MUST stay identical to backend/pipelines/billing/generate.py, because
    BillingSignal's natural key is (zone_id, period_start, period_end). Matching it means
    R2's real pipeline *upserts over* the seeded row rather than inserting a second,
    competing one.

    Do not "improve" this into a rolling window. It used to be observed-33d..observed-3d,
    whose period_end is later than anything the real generator produces -- so fusion's
    "latest billing row per zone" lookup kept picking the seeded figures forever, and every
    zone showed fake NRW even after real data had ingested successfully.
    """
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def make_polygon(lat: float, lon: float) -> dict:
    half = CELL / 2
    ring = [
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def build_zones(city: str, count: int) -> list[Zone]:
    lat0, lon0 = CITY_CENTRES.get(city, CITY_CENTRES["Jaipur"])
    cols = 6
    zones = []
    for i in range(count):
        row, col = divmod(i, cols)
        lat = lat0 + (row - count / cols / 2) * CELL
        lon = lon0 + (col - cols / 2) * CELL
        zones.append(
            Zone(
                id=f"Z-{i + 1:03d}",
                name=f"Ward {row + 1} - Sector {col + 1}",
                city=city,
                ward=f"Ward {row + 1}",
                centroid_lat=round(lat, 6),
                centroid_lon=round(lon, 6),
                geojson=make_polygon(lat, lon),
                pipe_length_km=round(RNG.uniform(3.0, 14.0), 2),
                population=RNG.randint(4_000, 22_000),
            )
        )
    return zones


SIGNALS = ("satellite", "billing", "citizen")


def seed(city: str, zone_count: int, skip: frozenset[str] = frozenset()) -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # Wipe in FK-safe order.
        for model in (ZoneScore, CitizenReport, SatelliteSignal, BillingSignal, Zone):
            db.execute(delete(model))
        db.commit()

        zones = build_zones(city, zone_count)
        db.add_all(zones)
        db.commit()

        # A handful of zones are the planted "real leaks" -- these should end up at the
        # top of the ranked list, with all three signals agreeing.
        hotspots = {z.id for z in RNG.sample(zones, k=max(3, zone_count // 8))}
        observed = date.today() - timedelta(days=3)
        now = datetime.now(timezone.utc)

        billing_start, billing_end = billing_period()

        for zone in zones:
            hot = zone.id in hotspots

            # Every value below is drawn whether or not its signal is skipped. Skipping
            # the RNG calls instead would shift the stream and silently change the other
            # signals' numbers, so `--skip satellite` would also move every billing
            # figure -- and the whole point of the fixed seed is a reproducible demo.
            # Only the inserts are conditional.

            # --- satellite: NDVI above a 3-year baseline over the pipe corridor
            baseline = round(RNG.uniform(0.24, 0.38), 3)
            anomaly = round(RNG.uniform(0.10, 0.22) if hot else RNG.gauss(0.01, 0.035), 3)
            sat_score = max(0.0, min(100.0, round(anomaly / 0.22 * 100, 2)))
            wetness = round(RNG.uniform(0.1, 0.6), 3)
            cloud = round(RNG.uniform(0, 15), 1)
            if "satellite" not in skip:
                db.add(
                    SatelliteSignal(
                        zone_id=zone.id,
                        observed_on=observed,
                        ndvi_mean=round(baseline + anomaly, 3),
                        ndvi_baseline=baseline,
                        ndvi_anomaly=anomaly,
                        wetness_index=wetness,
                        cloud_pct=cloud,
                        score=sat_score,
                        source="seed",
                    )
                )

            # --- billing: non-revenue water. National average sits around 30-40%.
            nrw = RNG.uniform(42, 58) if hot else RNG.uniform(12, 38)
            supplied = round(RNG.uniform(9_000, 40_000), 1)
            billed = round(supplied * (1 - nrw / 100), 1)
            if "billing" not in skip:
                db.add(
                    BillingSignal(
                        zone_id=zone.id,
                        period_start=billing_start,
                        period_end=billing_end,
                        supplied_kl=supplied,
                        billed_kl=billed,
                        nrw_pct=round(nrw, 2),
                        # 0% NRW -> 0, 60%+ NRW -> 100
                        score=round(max(0.0, min(100.0, nrw / 60 * 100)), 2),
                        is_synthetic=True,
                    )
                )

            # --- citizen: hotspots get several reports, most zones get none
            report_count = RNG.randint(2, 6) if hot else RNG.choices([0, 1], [0.8, 0.2])[0]
            for n in range(report_count):
                report = CitizenReport(
                    zone_id=zone.id,
                    reported_at=now - timedelta(days=RNG.randint(0, 25), hours=n),
                    channel=RNG.choice(["whatsapp", "web"]),
                    reporter_hash=f"sha256:seed{RNG.randint(10**6, 10**7)}",
                    description=RNG.choice(
                        [
                            "Water flowing on the road since morning",
                            "Road is always wet near the corner, no rain here",
                            "Low pressure for a week and water on the street",
                            "Pipeline leaking beside the school gate",
                        ]
                    ),
                    lat=zone.centroid_lat + RNG.uniform(-CELL / 3, CELL / 3),
                    lon=zone.centroid_lon + RNG.uniform(-CELL / 3, CELL / 3),
                    status="new",
                )
                if "citizen" not in skip:
                    db.add(report)

        db.commit()
        scored = run_fusion(db, city)
        seeded = ", ".join(s for s in SIGNALS if s not in skip) or "no signals"
        print(f"seeded {len(zones)} zones in {city}, planted {len(hotspots)} leak hotspots")
        print(f"signals seeded: {seeded}")
        if skip:
            print(f"skipped: {', '.join(sorted(skip))} -- real pipelines own these now")
        print(f"fusion scored {scored} zones -- try: curl localhost:8000/api/scores | head")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default=settings.city_default)
    parser.add_argument("--zones", type=int, default=30)
    parser.add_argument(
        "--skip",
        default="",
        help=(
            "comma-separated signals NOT to seed (satellite,billing,citizen). Use this when a "
            "real pipeline owns that signal: seeding it anyway invents readings for zones that "
            "genuinely have none, e.g. the zones with no cloud-free satellite pixel."
        ),
    )
    args = parser.parse_args()

    skip = frozenset(s.strip().lower() for s in args.skip.split(",") if s.strip())
    unknown = skip - set(SIGNALS)
    if unknown:
        parser.error(f"unknown signal(s) {', '.join(sorted(unknown))}; pick from {', '.join(SIGNALS)}")

    seed(args.city, args.zones, skip)
