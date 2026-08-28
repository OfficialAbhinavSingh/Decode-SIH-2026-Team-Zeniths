import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CitizenReport, Zone
from ..schemas import ReportIn, ReportOut
from ..services.geo import point_in_geojson
from ..services.relevance import classify

router = APIRouter(prefix="/api/reports", tags=["reports"])

# automation/n8n is a sibling of backend/, not a package under it -- reached across the
# monorepo on purpose so both the live endpoint and the n8n workflow share one
# deduplication rule. On Render this import always fails: render.yaml sets `rootDir:
# backend` for this service, so automation/ never ships with the deployed build, and
# dedup silently no-ops there. Locally and in docker-compose (full checkout) it works.
sys.path.append(str(Path(__file__).resolve().parents[3] / "automation" / "n8n"))
try:
    from utils.dedupe import ReportDeduplicator
except ImportError:
    ReportDeduplicator = None

deduplicator = ReportDeduplicator() if ReportDeduplicator else None


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

    # A greeting or an unrelated civic complaint is stored, not rejected -- the resident
    # still gets a receipt and we keep the audit trail -- but it must not score as leak
    # evidence. Production had `/help`, `Hello?`, `Pothole` and `Pothole damage` all
    # counting toward one zone's citizen score, which carried it to rank 6 of 30.
    # `dismissed` is the status fusion already excludes, so this needs no scoring change.
    relevance = classify(payload.description)
    status = "new" if relevance == "actionable" else "dismissed"
    if status == "dismissed":
        print(f"Report stored but not scored ({relevance}): {payload.description!r}")
    # Only dedupe reports that carry a real reporter_hash. The web-form fallback
    # (frontend/src/pages/Report.jsx) never sends one, so every anonymous submission has
    # reporter_hash=None -- without this guard the deduplicator's `past.reporter_hash ==
    # reporter_hash` check matches None-against-None and silently drops the second
    # anonymous report from two different people, which is exactly the path
    # docs/SCOPE.md calls "must never break."
    if deduplicator and payload.reporter_hash:
        is_dup, reason, cluster_count = deduplicator.check_and_record(
            reporter_hash=payload.reporter_hash,
            lat=payload.lat,
            lon=payload.lon,
            zone_id=zone_id,
            description=payload.description,
        )
        if is_dup and status == "new":
            print(f"Dropped duplicate report: {reason}")
            status = "duplicate"

    report = CitizenReport(
        zone_id=zone_id,
        channel=payload.channel,
        reporter_hash=payload.reporter_hash,
        description=payload.description,
        lat=payload.lat,
        lon=payload.lon,
        media_url=payload.media_url,
        status=status,
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
