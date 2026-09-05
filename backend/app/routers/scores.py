from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Zone, ZoneScore
from ..schemas import ScoreOut

router = APIRouter(prefix="/api/scores", tags=["scores"])


def _ranked(db: Session, city: str, limit: int | None):
    stmt = (
        select(ZoneScore, Zone)
        .join(Zone, ZoneScore.zone_id == Zone.id)
        .where(Zone.city == city)
        .order_by(ZoneScore.rank)
    )
    if limit:
        stmt = stmt.limit(limit)
    return db.execute(stmt).all()


@router.get("", response_model=list[ScoreOut])
def list_scores(
    city: str = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    city = city or settings.city_default
    return [
        {
            "zone_id": score.zone_id,
            "name": zone.name,
            "rank": score.rank,
            "fusion_score": score.fusion_score,
            "confidence": score.confidence,
            "signals_used": score.signals_used,
            "satellite_score": score.satellite_score,
            "billing_score": score.billing_score,
            "citizen_score": score.citizen_score,
            "explanation": score.explanation,
            "computed_at": score.computed_at,
        }
        for score, zone in _ranked(db, city, limit)
    ]


@router.get("/geojson")
def scores_geojson(
    city: str = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """One request that paints the whole map: polygons with their fusion score attached."""
    city = city or settings.city_default
    features = [
        {
            "type": "Feature",
            "geometry": zone.geojson.get("geometry", zone.geojson),
            "properties": {
                "zone_id": zone.id,
                "name": zone.name,
                "ward": zone.ward,
                # R4 labels the list "N zones in <city>, ranked". Carrying the city here
                # keeps that label truthful for any city instead of hardcoding Jaipur in
                # the frontend. Additive -- no existing consumer reads it.
                "city": zone.city,
                "rank": score.rank,
                "fusion_score": score.fusion_score,
                "confidence": score.confidence,
                "signals_used": score.signals_used,
                "explanation": score.explanation,
            },
        }
        for score, zone in _ranked(db, city, None)
    ]
    return {"type": "FeatureCollection", "features": features}
