"""Read a Google Earth Engine CSV export, score it, POST it to the API.

    python -m pipelines.satellite.load data/samples/ndvi_export.csv

Expected CSV columns: zone_id, observed_on, ndvi_mean, ndvi_baseline
Optional: cloud_pct, wetness_index
"""

import argparse
import csv
import os
import sys

import httpx

from .ndvi import score_batch


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    "zone_id": raw["zone_id"].strip(),
                    "observed_on": raw["observed_on"].strip(),
                    "ndvi_mean": float(raw["ndvi_mean"]),
                    "ndvi_baseline": float(raw["ndvi_baseline"]),
                    "cloud_pct": float(raw["cloud_pct"]) if raw.get("cloud_pct") else None,
                    "wetness_index": (
                        float(raw["wetness_index"]) if raw.get("wetness_index") else None
                    ),
                    "source": "sentinel2-gee",
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.environ.get("INGEST_TOKEN", "dev-ingest-token"))
    parser.add_argument("--dry-run", action="store_true", help="score and print, don't POST")
    args = parser.parse_args()

    rows = score_batch(read_csv(args.csv_path))
    print(f"scored {len(rows)} zones, top 5 by score:")
    for row in sorted(rows, key=lambda r: r["score"], reverse=True)[:5]:
        print(f"  {row['zone_id']}  anomaly={row['ndvi_anomaly']:+.3f}  score={row['score']}")

    if args.dry_run:
        return 0

    response = httpx.post(
        f"{args.url}/api/ingest/satellite",
        json=rows,
        headers={"X-Ingest-Token": args.token},
        timeout=60,
    )
    if response.status_code >= 400:
        print(f"ingest failed {response.status_code}: {response.text}", file=sys.stderr)
        return 1
    print("ingested:", response.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
