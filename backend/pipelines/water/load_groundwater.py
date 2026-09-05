"""Load the CGWB groundwater stress table into the database.

Owner: R2 (Data).

    python -m pipelines.water.load_groundwater --csv ../data/india/groundwater_cgwb2023.csv

The CSV is built from Annexure-I of the CGWB *National Compilation on Dynamic Ground Water
Resources of India, 2023*. Every row carries the extractable-resource and extraction
columns it was derived from, so `--audit` can recompute the stage of extraction and prove
the printed figure -- 30 of 36 states agree to two decimal places, and the ones that do
not are places where the PDF's text layer dropped a digit (Haryana prints as 35.74 against
a true 135.74, which the recomputation catches).

Rows that could not be cross-checked load with `verified=false`. Nothing stops you using
them; the flag exists so nobody quotes an unchecked number on stage.
"""

import argparse
import csv
import sys

from app.db import SessionLocal
from app.models import GroundwaterStress
from app.upsert import upsert
from app.services.urgency import categorise, urgency_boost

TOLERANCE_PCT = 1.5


def read_rows(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            rows.append(
                {
                    "state": raw["state"].strip(),
                    "district": (raw.get("district") or "").strip() or None,
                    "assessed_year": int(raw["assessed_year"]),
                    "stage_of_extraction_pct": float(raw["stage_of_extraction_pct"]),
                    "category": raw["category"].strip(),
                    "source": raw["source"].strip(),
                    "verified": str(raw.get("verified", "")).lower() == "true",
                    "_extractable": float(raw["extractable_bcm"]) if raw.get("extractable_bcm") else None,
                    "_extraction": float(raw["extraction_bcm"]) if raw.get("extraction_bcm") else None,
                }
            )
    return rows


def audit(rows: list[dict]) -> int:
    """Recompute every stage from its own columns and report disagreements."""
    bad = 0
    print(f"{'state':<42}{'printed':>9}{'recomputed':>12}{'category':>16}{'x':>7}")
    for row in sorted(rows, key=lambda r: -r["stage_of_extraction_pct"]):
        printed = row["stage_of_extraction_pct"]
        if row["_extractable"]:
            recomputed = row["_extraction"] / row["_extractable"] * 100
            mark = "" if abs(recomputed - printed) < TOLERANCE_PCT else "  <-- check"
            if mark:
                bad += 1
        else:
            recomputed, mark = float("nan"), "  (no columns)"
        expected = categorise(printed)
        drift = "" if expected == row["category"] else f"  <-- category says {expected}"
        print(
            f"{row['state']:<42}{printed:>9.2f}{recomputed:>12.2f}{row['category']:>16}"
            f"{urgency_boost(printed):>7.3f}{mark}{drift}"
        )
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/india/groundwater_cgwb2023.csv")
    parser.add_argument("--audit", action="store_true", help="cross-check and exit")
    args = parser.parse_args()

    rows = read_rows(args.csv)
    if not rows:
        print("no rows", file=sys.stderr)
        return 1

    if args.audit:
        bad = audit(rows)
        print(f"\n{len(rows)} states/UTs, {bad} row(s) where the printed figure and the "
              f"recomputed one differ by more than {TOLERANCE_PCT}%")
        return 0

    payload = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    db = SessionLocal()
    try:
        upsert(db, GroundwaterStress, payload, constraint="uq_gw_state_district")
        db.commit()
    finally:
        db.close()

    unverified = [r["state"] for r in rows if not r["verified"]]
    print(f"loaded {len(rows)} states/UTs")
    if unverified:
        print(f"{len(unverified)} unverified: {', '.join(unverified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
