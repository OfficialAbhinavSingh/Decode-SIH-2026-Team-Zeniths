from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CitizenReport, Zone
from ..schemas import ReportIn, ReportOut
from ..services.geo import point_in_geojson

router = APIRouter(prefix="/api/reports", tags=["reports"])


def match_zone(db: Session, lat: float, lon: float) -> str | None:
    """Find the zone whose polygon contains this point. None if it falls outside every zone."""
    for zone in db.scalars(select(Zone)).all():
        geometry = zone.geojson.get("geometry", zone.geojson)
        if point_in_geojson(lon, lat, geometry):
            return zone.id
    return None


@router.post("", response_model=ReportOut, status_code=201)
def create_report(payload: ReportIn, db: Session = Depends(get_db)) -> CitizenReport:
    zone_id = payload.zone_id
    if zone_id is None and payload.lat is not None and payload.lon is not None:
        zone_id = match_zone(db, payload.lat, payload.lon)

    report = CitizenReport(
        zone_id=zone_id,
        channel=payload.channel,
        reporter_hash=payload.reporter_hash,
        description=payload.description,
        lat=payload.lat,
        lon=payload.lon,
        media_url=payload.media_url,
        status="new",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("", response_model=list[ReportOut])
def list_reports(limit: int = 100, db: Session = Depends(get_db)) -> list[CitizenReport]:
    return list(
        db.scalars(
            select(CitizenReport).order_by(CitizenReport.reported_at.desc()).limit(limit)
        ).all()
    )
