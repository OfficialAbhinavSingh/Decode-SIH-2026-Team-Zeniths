"""Seed synthetic zones and signals for Indian cities. Owner: R1 (Satellite & Geo).

    python -m pipelines.synthetic.seed_india                    # every city in the registry
    python -m pipelines.synthetic.seed_india --cities Jaipur,Pune
    python -m pipelines.synthetic.seed_india --states Rajasthan,Kerala
    python -m pipelines.synthetic.seed_india --limit 20         # the 20 largest
    python -m pipelines.synthetic.seed_india --dry-run          # count, write nothing

    # Adding the country to a database that already holds a real city, without touching it:
    python -m pipelines.synthetic.seed_india --keep --exclude Jaipur

This is `seed.py` widened from one city to the whole registry. It writes ONLY to the five
tables that already exist in docs/DATA-CONTRACT.md -- zones, satellite_signals,
billing_signals, citizen_reports, zone_scores -- and adds no column to any of them.

That constraint is the point, not an accident. The previous attempt at national coverage
added nullable columns to `zones` and `zone_scores`; `init_db.py` runs create_all(), which
creates missing *tables* and never alters existing ones, so those columns never appeared in
the deployed Postgres and every endpoint that selected a Zone returned 500. Staying inside
the frozen schema means this script needs no migration and cannot repeat that.

Data written here is synthetic. See grid.py's module docstring for exactly what that means.
"""

import argparse
import sys
import time

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import BillingSignal, CitizenReport, SatelliteSignal, Zone, ZoneScore
from app.services.fusion import run_fusion

from .cities import CITIES, ZONES_PER_TIER, City, get
from .grid import build_city

# Rows per executemany. Small enough to stay under SQLite's 999-variable statement limit
# for the widest table here, large enough that a 6,000-zone run is not thousands of round
# trips to a remote Postgres.
CHUNK = 400

TIER_ORDER = sorted(ZONES_PER_TIER, key=lambda t: -ZONES_PER_TIER[t])


def _insert_rows(db: Session, model, rows: list[dict]) -> None:
    for start in range(0, len(rows), CHUNK):
        db.execute(insert(model), rows[start : start + CHUNK])


def select_cities(
    names: str, states: str, limit: int | None, exclude: str = ""
) -> list[City]:
    """Resolve the CLI filters to a city list, largest first."""
    chosen = list(CITIES)
    if names:
        chosen = [get(n.strip()) for n in names.split(",") if n.strip()]
    if states:
        wanted = {s.strip().lower() for s in states.split(",") if s.strip()}
        chosen = [c for c in chosen if c.state.lower() in wanted]
        if not chosen:
            raise SystemExit(f"no cities in {states!r}; try one of: {', '.join(sorted({c.state for c in CITIES}))}")
    if exclude:
        # get() rather than a bare string compare, so a typo is a loud KeyError naming the
        # closest match instead of a silent no-op that quietly seeds the city you were
        # trying to protect.
        dropped = {get(n.strip()).name for n in exclude.split(",") if n.strip()}
        chosen = [c for c in chosen if c.name not in dropped]
        if not chosen:
            raise SystemExit(f"--exclude {exclude!r} removed every selected city")
    chosen.sort(key=lambda c: (TIER_ORDER.index(c.tier), c.name))
    if limit:
        chosen = chosen[:limit]
    return chosen


def wipe(db: Session) -> None:
    """Clear every table this script owns, in FK-safe order.

    Same wipe-and-rebuild contract as seed.py: re-running must reset, not accumulate. It
    deletes citizen reports too, including any a real resident submitted through the web
    form -- which is correct for a demo database and would not be for a live one.
    """
    for model in (ZoneScore, CitizenReport, SatelliteSignal, BillingSignal, Zone):
        db.execute(delete(model))
    db.commit()


def seed(cities: list[City], keep: bool = False) -> tuple[int, int]:
    """Write the grid and signals for `cities`, then score each one. Returns (zones, scored)."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if not keep:
            wipe(db)

        total_zones = 0
        total_scored = 0
        started = time.monotonic()

        for index, city in enumerate(cities, start=1):
            zones, signals = build_city(city)

            # --- one city at a time, committed before the next starts.
            #
            # A single transaction across 230 cities means one bad row loses the entire
            # run, and on a remote database it also means holding a write transaction open
            # for minutes. Per-city commits make a failure cost one city, and let a run
            # that is interrupted halfway leave a database that is smaller than intended
            # but entirely coherent -- every city present is complete and scored.
            _insert_rows(db, Zone, zones)
            db.commit()
            for model, key in (
                (SatelliteSignal, "satellite"),
                (BillingSignal, "billing"),
                (CitizenReport, "citizen"),
            ):
                _insert_rows(db, model, signals[key])
            db.commit()

            scored = run_fusion(db, city.name)
            total_zones += len(zones)
            total_scored += scored

            elapsed = time.monotonic() - started
            print(
                f"[{index:>3}/{len(cities)}] {city.name:<28} {city.state:<38} "
                f"{len(zones):>3} zones  {scored:>3} scored  {elapsed:6.1f}s",
                flush=True,
            )

        return total_zones, total_scored
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="", help="comma-separated city names")
    parser.add_argument("--states", default="", help="comma-separated states/UTs")
    parser.add_argument("--limit", type=int, help="keep only the N largest of the selection")
    parser.add_argument(
        "--exclude",
        default="",
        help="comma-separated city names to leave out. The reason this exists: a deployed "
        "database already holds one real city, and --keep does plain inserts, so a run "
        "that reaches a city already present dies on its primary key. "
        "`--keep --exclude Jaipur` adds the other 233 and leaves the real one alone.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="do NOT wipe first. Only safe for cities not already in the database -- "
        "zone ids are unique per city, so re-seeding one that is present will fail on "
        "the primary key rather than replace it.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report the plan, write nothing")
    args = parser.parse_args()

    cities = select_cities(args.cities, args.states, args.limit, args.exclude)
    zones = sum(c.zone_count for c in cities)
    states = len({c.state for c in cities})
    print(f"{len(cities)} cities across {states} states/UTs -> {zones} zones")

    if args.dry_run:
        for city in cities:
            print(f"  {city.code:<5} {city.name:<28} {city.state:<38} {city.zone_count:>3} zones")
        print("dry run -- nothing written")
        return 0

    written, scored = seed(cities, keep=args.keep)
    print(f"\nwrote {written} zones, fusion scored {scored}")
    print("try: curl 'localhost:8000/api/cities' and 'localhost:8000/api/scores?city=Pune'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
