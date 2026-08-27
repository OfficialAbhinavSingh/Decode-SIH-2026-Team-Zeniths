"""Score a billing CSV and POST it to the API.

Owner: R2 · Saksham (@Saksham0423).

Usage:
    # Dry run — score locally, print summary table, no network call
    python -m pipelines.billing.load data/samples/billing.csv --dry-run

    # Live ingest to the local dev server
    python -m pipelines.billing.load data/samples/billing.csv

    # Live ingest to a deployed Render instance
    python -m pipelines.billing.load data/samples/billing.csv --url https://neerdrishti.onrender.com

The INGEST_TOKEN env var (or --token flag) must match what the API expects.
Default for local dev: "dev-ingest-token" (set in .env.example).
"""

import argparse
import csv
import os
import sys
import time

# pyrefly: ignore [missing-import]
import httpx

from .nrw import score_batch_with_percentile


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------


def read_csv(path: str) -> list[dict]:
    """Read the billing CSV produced by generate.py.

    Normalises types: zone_id is stripped, numeric fields are float.
    ``is_synthetic`` is hardcoded True — our dataset is always synthetic.
    """
    with open(path, newline="", encoding="utf-8") as fh:
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


# ---------------------------------------------------------------------------
# API ingest (with simple retry)
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_DELAY_S = 2.0


def post_to_api(rows: list[dict], url: str, token: str) -> dict:
    """POST scored rows to /api/ingest/billing.

    Retries up to _MAX_RETRIES times on network errors or 5xx responses.
    Raises RuntimeError on final failure so the caller can exit non-zero.
    """
    target = f"{url}/api/ingest/billing"
    headers = {"X-Ingest-Token": token}

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = httpx.post(target, json=rows, headers=headers, timeout=60)
        except httpx.RequestError as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"network error after {attempt} attempts: {exc}") from exc
            print(f"  [retry {attempt}/{_MAX_RETRIES}] network error: {exc}", file=sys.stderr)
            time.sleep(_RETRY_DELAY_S)
            continue

        if resp.status_code < 400:
            return resp.json()

        # 4xx → no point retrying (bad request, bad token, unknown zone_id)
        if resp.status_code < 500:
            raise RuntimeError(
                f"ingest rejected ({resp.status_code}): {resp.text}\n"
                "Common causes: wrong INGEST_TOKEN, zone_ids not in DB (run seed.py first)."
            )

        # 5xx → server-side, worth retrying
        if attempt == _MAX_RETRIES:
            raise RuntimeError(f"server error after {attempt} attempts ({resp.status_code}): {resp.text}")
        print(f"  [retry {attempt}/{_MAX_RETRIES}] server error {resp.status_code}", file=sys.stderr)
        time.sleep(_RETRY_DELAY_S)

    raise RuntimeError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# Dry-run summary printer
# ---------------------------------------------------------------------------

_COL_WIDTH = {
    "zone_id": 8,
    "nrw_pct": 9,
    "score": 7,
    "supplied_kl": 12,
    "billed_kl": 11,
}

_HOTSPOT_THRESHOLD = 65.0  # score above this = likely planted leak zone


def _flag(score: float) -> str:
    return "[HOTSPOT]" if score >= _HOTSPOT_THRESHOLD else ""


def print_summary(rows: list[dict]) -> None:
    """Print a human-readable scored table to stdout.

    Sorted worst-first so a reviewer can immediately see the top zones.
    The 🔴 HOTSPOT flag makes it easy to confirm the planted zones are at the top.
    """
    sorted_rows = sorted(rows, key=lambda r: r["score"], reverse=True)

    header = (
        f"{'zone_id':<8}  {'nrw_pct':>9}  {'score':>7}  {'supplied_kl':>12}  {'billed_kl':>11}  note"
    )
    sep = "-" * len(header)
    print(f"\nScored {len(rows)} zones — worst first:\n{sep}\n{header}\n{sep}")
    for r in sorted_rows:
        print(
            f"{r['zone_id']:<8}  "
            f"{r['nrw_pct']:>9.2f}  "
            f"{r['score']:>7.1f}  "
            f"{r['supplied_kl']:>12,.1f}  "
            f"{r['billed_kl']:>11,.1f}  "
            f"{_flag(r['score'])}"
        )
    print(sep)

    hotspots = [r for r in rows if r["score"] >= _HOTSPOT_THRESHOLD]
    print(f"\nHotspot zones (score >= {_HOTSPOT_THRESHOLD}): {len(hotspots)}")
    if not hotspots:
        print(
            "  WARNING: no hotspot zones found. "
            "Regenerate billing.csv with --hotspots <zone_ids> so the demo has an agreement story."
        )
    else:
        for r in sorted(hotspots, key=lambda r: r["score"], reverse=True):
            print(f"  {r['zone_id']}  nrw={r['nrw_pct']:.1f}%  score={r['score']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="path to billing CSV (e.g. data/samples/billing.csv)")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--token",
        default=os.environ.get("INGEST_TOKEN", "dev-ingest-token"),
        help="X-Ingest-Token header value (default: $INGEST_TOKEN or 'dev-ingest-token')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="score and print summary without hitting the API",
    )
    args = parser.parse_args()

    rows = read_csv(args.csv_path)
    print(f"read {len(rows)} rows from {args.csv_path}")

    score_batch_with_percentile(rows)

    print_summary(rows)

    if args.dry_run:
        print("\n[dry-run] skipping API call.")
        return 0

    print(f"\nPosting to {args.url}/api/ingest/billing ...")
    try:
        result = post_to_api(rows, args.url, args.token)
    except RuntimeError as exc:
        print(f"\n[FAILED] ingest failed: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] ingested: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
