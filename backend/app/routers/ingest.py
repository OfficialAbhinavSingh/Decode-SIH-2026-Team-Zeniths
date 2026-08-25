"""Bulk ingest endpoints for the two offline pipelines (R1 satellite, R2 billing).

Protected by a shared token so a stranger can't poison the public map.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import BillingSignal, SatelliteSignal, Zone
from ..schemas import BillingSignalIn, IngestResult, SatelliteSignalIn

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def require_token(x_ingest_token: str = Header(default="")) -> None:
    if x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=401, detail="bad or missing X-Ingest-Token")


def _upsert(db: Session, table, rows: list[dict], conflict_cols: list[str]) -> int:
    """Insert rows, or overwrite the existing row on the natural-key conflict.

    DATA-CONTRACT.md calls both ingest endpoints "bulk upsert" -- re-running a pipeline for
    a day/period it already reported must correct that row, not duplicate it.
    """
    if not rows:
        return 0
    update_cols = {c: getattr(insert(table).excluded, c) for c in rows[0] if c not in conflict_cols}
    stmt = insert(table).values(rows).on_conflict_do_update(
        index_elements=conflict_cols, set_=update_cols
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


@router.post("/satellite", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_satellite(
    rows: list[SatelliteSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    for row in rows:
        if db.get(Zone, row.zone_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown zone_id {row.zone_id}")
    inserted = _upsert(
        db, SatelliteSignal, [row.model_dump() for row in rows], ["zone_id", "observed_on"]
    )
    return {"inserted": inserted}


@router.post("/billing", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_billing(
    rows: list[BillingSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    for row in rows:
        if db.get(Zone, row.zone_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown zone_id {row.zone_id}")
    inserted = _upsert(
        db, BillingSignal, [row.model_dump() for row in rows], ["zone_id", "period_start", "period_end"]
    )
    return {"inserted": inserted}
