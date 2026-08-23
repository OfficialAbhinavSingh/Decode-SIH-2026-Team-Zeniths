"""Bulk ingest endpoints for the two offline pipelines (R1 satellite, R2 billing).

Protected by a shared token so a stranger can't poison the public map.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import BillingSignal, SatelliteSignal, Zone
from ..schemas import BillingSignalIn, IngestResult, SatelliteSignalIn

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def require_token(x_ingest_token: str = Header(default="")) -> None:
    if x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=401, detail="bad or missing X-Ingest-Token")


@router.post("/satellite", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_satellite(
    rows: list[SatelliteSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    inserted = 0
    for row in rows:
        if db.get(Zone, row.zone_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown zone_id {row.zone_id}")
        db.add(SatelliteSignal(**row.model_dump()))
        inserted += 1
    db.commit()
    return {"inserted": inserted}


@router.post("/billing", response_model=IngestResult, dependencies=[Depends(require_token)])
def ingest_billing(
    rows: list[BillingSignalIn],
    db: Session = Depends(get_db),
) -> dict:
    inserted = 0
    for row in rows:
        if db.get(Zone, row.zone_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown zone_id {row.zone_id}")
        db.add(BillingSignal(**row.model_dump()))
        inserted += 1
    db.commit()
    return {"inserted": inserted}
