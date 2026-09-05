"""Load the per-city rainfall table into the database.

Owner: R2 (Data). Run `pipelines.water.rainfall` first to produce the CSV, or point this
at a file n8n's scheduled job has already written.

    python -m pipelines.water.load_rainfall --csv ../data/india/rainfall.csv
"""

import argparse
import csv
import sys
from datetime import date

from app.db import SessionLocal
from app.models import RainfallObservation
from app.upsert import upsert

from .rainfall import RAIN_SUSPECT_MM_7D, satellite_confidence


def read_rows(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        return [
            {
                "city_code": raw["city_code"].strip(),
                "observed_on": date.fromisoformat(raw["observed_on"]),
                "rain_mm_7d": float(raw["rain_mm_7d"]),
                "rain_mm_30d": float(raw["rain_mm_30d"]),
                "source": raw.get("source") or "open-meteo-era5",
            }
            for raw in csv.DictReader(fh)
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/india/rainfall.csv")
    args = parser.parse_args()

    rows = read_rows(args.csv)
    if not rows:
        print("no rows", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        upsert(db, RainfallObservation, rows, constraint="uq_rain_city_day")
        db.commit()
    finally:
        db.close()

    wet = [r for r in rows if r["rain_mm_7d"] > RAIN_SUSPECT_MM_7D]
    print(f"loaded {len(rows)} city rainfall rows")
    print(f"{len(wet)} over {RAIN_SUSPECT_MM_7D:.0f} mm/7d -- satellite weight reduced in those cities")
    for row in sorted(rows, key=lambda r: -r["rain_mm_7d"])[:5]:
        print(f"  {row['city_code']}  {row['rain_mm_7d']:6.1f} mm  weight x{satellite_confidence(row['rain_mm_7d'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
