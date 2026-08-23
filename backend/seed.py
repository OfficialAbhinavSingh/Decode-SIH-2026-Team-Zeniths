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


def seed(city: str, zone_count: int) -> None:
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

        for zone in zones:
            hot = zone.id in hotspots

            # --- satellite: NDVI above a 3-year baseline over the pipe corridor
            baseline = round(RNG.uniform(0.24, 0.38), 3)
            anomaly = round(RNG.uniform(0.10, 0.22) if hot else RNG.gauss(0.01, 0.035), 3)
            sat_score = max(0.0, min(100.0, round(anomaly / 0.22 * 100, 2)))
            db.add(
                SatelliteSignal(
                    zone_id=zone.id,
                    observed_on=observed,
                    ndvi_mean=round(baseline + anomaly, 3),
                    ndvi_baseline=baseline,
                    ndvi_anomaly=anomaly,
                    wetness_index=round(RNG.uniform(0.1, 0.6), 3),
                    cloud_pct=round(RNG.uniform(0, 15), 1),
                    score=sat_score,
                    source="seed",
                )
            )

            # --- billing: non-revenue water. National average sits around 30-40%.
            nrw = RNG.uniform(42, 58) if hot else RNG.uniform(12, 38)
            supplied = round(RNG.uniform(9_000, 40_000), 1)
            billed = round(supplied * (1 - nrw / 100), 1)
            db.add(
                BillingSignal(
                    zone_id=zone.id,
                    period_start=observed - timedelta(days=33),
                    period_end=observed - timedelta(days=3),
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
                db.add(
                    CitizenReport(
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
                )

        db.commit()
        scored = run_fusion(db, city)
        print(f"seeded {len(zones)} zones in {city}, planted {len(hotspots)} leak hotspots")
        print(f"fusion scored {scored} zones -- try: curl localhost:8000/api/scores | head")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default=settings.city_default)
    parser.add_argument("--zones", type=int, default=30)
    args = parser.parse_args()
    seed(args.city, args.zones)
