from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import BillingSignal, CitizenReport, SatelliteSignal, Zone
from ..schemas import ZoneOut, ZoneSignalsOut

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", response_model=list[ZoneOut])
def list_zones(
    city: str = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Zone]:
    city = city or settings.city_default
    return list(db.scalars(select(Zone).where(Zone.city == city).order_by(Zone.id)).all())


@router.get("/{zone_id}", response_model=ZoneOut)
def get_zone(zone_id: str, db: Session = Depends(get_db)) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")
    return zone


@router.get("/{zone_id}/signals", response_model=ZoneSignalsOut)
def get_zone_signals(zone_id: str, db: Session = Depends(get_db)) -> dict:
    if db.get(Zone, zone_id) is None:
        raise HTTPException(status_code=404, detail=f"zone {zone_id} not found")

    return {
        "satellite": list(
            db.scalars(
                select(SatelliteSignal)
                .where(SatelliteSignal.zone_id == zone_id)
                .order_by(SatelliteSignal.observed_on.desc())
                .limit(12)
            ).all()
        ),
        "billing": list(
            db.scalars(
                select(BillingSignal)
                .where(BillingSignal.zone_id == zone_id)
                .order_by(BillingSignal.period_end.desc())
                .limit(12)
            ).all()
        ),
        "citizen": list(
            db.scalars(
                select(CitizenReport)
                .where(CitizenReport.zone_id == zone_id)
                .order_by(CitizenReport.reported_at.desc())
                .limit(50)
            ).all()
        ),
    }
