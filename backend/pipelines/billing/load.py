"""Score a billing CSV and POST it to the API.

    python -m pipelines.billing.load data/samples/billing.csv
"""

import argparse
import csv
import os
import sys

import httpx

from .nrw import score_batch


def read_csv(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        return [
            {
                "zone_id": raw["zone_id"].strip(),
                "period_start": raw["period_start"].strip(),
                "period_end": raw["period_end"].strip(),
                "supplied_kl": float(raw["supplied_kl"]),
                "billed_kl": float(raw["billed_kl"]),
                "is_synthetic": True,
            }
            for raw in csv.DictReader(fh)
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--token", default=os.environ.get("INGEST_TOKEN", "dev-ingest-token"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = score_batch(read_csv(args.csv_path))
    print(f"scored {len(rows)} zones, worst 5 by NRW:")
    for row in sorted(rows, key=lambda r: r["nrw_pct"], reverse=True)[:5]:
        print(f"  {row['zone_id']}  nrw={row['nrw_pct']:.1f}%  score={row['score']}")

    if args.dry_run:
        return 0

    response = httpx.post(
        f"{args.url}/api/ingest/billing",
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
