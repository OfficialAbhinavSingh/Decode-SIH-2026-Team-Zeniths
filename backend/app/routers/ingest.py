"""Bulk ingest endpoints for the two offline pipelines (R1 satellite, R2 billing).

Protected by a shared token so a stranger can't poison the public map.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import BillingSignal, SatelliteSignal, Zone
from ..schemas import BillingSignalIn, IngestResult, SatelliteSignalIn
# `dedupe` re-exported as `_dedupe`: this router had its own copy of the identical
# collapse-on-conflict-key logic before `app/upsert.py` existed to share it with the
# pipeline loaders. Kept importable under its original name -- tests/test_ingest_upsert.py
# imports it directly -- rather than duplicating the implementation a second time.
from ..upsert import dedupe as _dedupe
from ..upsert import upsert

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def require_token(x_ingest_token: str = Header(default="")) -> None:
    if x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=401, detail="bad or missing X-Ingest-Token")


def _upsert(db: Session, table, rows: list[dict], conflict_cols: list[str]) -> int:
    """Insert rows, or overwrite the existing row on the natural-key conflict.

    DATA-CONTRACT.md calls both ingest endpoints "bulk upsert" -- re-running a pipeline for
    a day/period it already reported must correct that row, not duplicate it.
    """
    rows = _dedupe(rows, conflict_cols)
    if not rows:
        return 0
    try:
        upsert(db, table, rows, index_elements=conflict_cols)
        db.commit()
    except (ProgrammingError, OperationalError) as exc:
        db.rollback()
        # Postgres reports a missing natural-key constraint as "no unique or exclusion
        # constraint"; SQLite (the offline-demo fallback DATABASE_URL, see app/upsert.py)
        # reports the equivalent case as "ON CONFLICT clause does not match any PRIMARY
        # KEY or UNIQUE constraint". Different dialect, same underlying problem, same fix.
        message = str(exc)
        if "no unique or exclusion constraint" not in message and "does not match any" not in message:
            raise
        # The natural-key constraints arrived with this pipeline. A database created before
        # them has the tables but not the index ON CONFLICT needs, and the driver reports
        # that as an opaque column-reference error. Say the actual fix instead.
        raise HTTPException(
            status_code=500,
            detail=(
                f"{table.__tablename__} is missing its natural-key unique constraint -- this "
                "database predates it. Drop the tables, then re-run `python -m app.init_db` "
                "and `python seed.py`."
            ),
        ) from exc
    return len(rows)


def _require_known_zones(db: Session, zone_ids: list[str]) -> None:
    """Reject the batch if any zone_id is unknown, in one query rather than one per row.

    A national ingest is several thousand rows; checking them with `db.get` per row is
    that many round trips and was the slowest part of a country-wide load. Reports the
    first few missing ids rather than just the count, so a mismatched zone scheme
    (`Z-014` against a `JAI-014` load) is obvious from the error alone.
    """
    wanted = set(zone_ids)
    if not wanted:
        return
    known = set(db.scalars(select(Zone.id).where(Zone.id.in_(wanted))).all())
    missing = sorted(wanted - known)
    if missing:
        shown = ", ".join(missing[:5])
        more = f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
        raise HTTPException(status_code=400, detail=f"unknown zone_id: {shown}{more}")


@router.post("/satellite", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_satellite(
    rows: list[SatelliteSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    _require_known_zones(db, [row.zone_id for row in rows])
    inserted = _upsert(
        db, SatelliteSignal, [row.model_dump() for row in rows], ["zone_id", "observed_on"]
    )
    return {"inserted": inserted}


@router.post("/billing", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_billing(
    rows: list[BillingSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    _require_known_zones(db, [row.zone_id for row in rows])
    inserted = _upsert(
        db, BillingSignal, [row.model_dump() for row in rows], ["zone_id", "period_start", "period_end"]
    )
    return {"inserted": inserted}
