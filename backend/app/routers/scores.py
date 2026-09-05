from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Zone, ZoneScore
from ..schemas import ScoreOut
from ..services import impact

router = APIRouter(prefix="/api/scores", tags=["scores"])


def _ranked(
    db: Session,
    city: str | None,
    limit: int | None,
    city_code: str | None = None,
    order_by_priority: bool = False,
):
    """Scored zones for one city.

    `city_code` is preferred over `city` now that coverage is national: two states can
    hold a city of the same name (there is a Hyderabad in Telangana and one in Sindh's
    namesake district lists, and India has several Amravati/Amaravati pairs), and the code
    is unique by construction. The `city` name filter stays because the MVP contract
    documents it and the existing dashboard sends it.
    """
    stmt = select(ZoneScore, Zone).join(Zone, ZoneScore.zone_id == Zone.id)
    if city_code:
        stmt = stmt.where(Zone.city_code == city_code)
    else:
        stmt = stmt.where(Zone.city == city)
    stmt = stmt.order_by(
        ZoneScore.priority_score.desc() if order_by_priority else ZoneScore.rank
    )
    if limit:
        stmt = stmt.limit(limit)
    return db.execute(stmt).all()


def _serialise(score: ZoneScore, zone: Zone) -> dict:
    kld = score.water_at_risk_kld or 0.0
    return {
        "zone_id": score.zone_id,
        "name": zone.name,
        "city": zone.city,
        "city_code": zone.city_code,
        "state": zone.state,
        "rank": score.rank,
        "fusion_score": score.fusion_score,
        "absolute_score": score.absolute_score,
        "priority_score": score.priority_score,
        "urgency_multiplier": score.urgency_multiplier,
        "groundwater_stress_pct": score.groundwater_stress_pct,
        "groundwater_category": score.groundwater_category,
        "rain_flagged": bool(score.rain_flagged),
        "rain_mm_7d": score.rain_mm_7d,
        "water_at_risk_kld": score.water_at_risk_kld,
        "annual_value_inr": impact.annual_value_inr(kld),
        "households_served": impact.households_served(kld),
        "confidence": score.confidence,
        "signals_used": score.signals_used,
        "satellite_score": score.satellite_score,
        "billing_score": score.billing_score,
        "citizen_score": score.citizen_score,
        "explanation": score.explanation,
        "computed_at": score.computed_at,
    }


@router.get("", response_model=list[ScoreOut])
def list_scores(
    city: str = Query(default=None),
    city_code: str = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    by_priority: bool = Query(
        default=False,
        description="order by priority_score (leak score lifted by groundwater stress) "
        "instead of the within-city rank",
    ),
    db: Session = Depends(get_db),
) -> list[dict]:
    city = city or (None if city_code else settings.city_default)
    return [
        _serialise(score, zone)
        for score, zone in _ranked(db, city, limit, city_code, by_priority)
    ]


@router.get("/geojson")
def scores_geojson(
    city: str = Query(default=None),
    city_code: str = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """One request that paints the whole map: polygons with their fusion score attached.

    Deliberately still one city at a time. At national zoom the map draws
    `/api/national/states` and `/api/national/cities` instead -- returning seven thousand
    polygons here would be ~3 MB and several seconds of Leaflet layout on a phone.
    """
    city = city or (None if city_code else settings.city_default)
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
                "priority_score": score.priority_score,
                "water_at_risk_kld": score.water_at_risk_kld,
                "groundwater_category": score.groundwater_category,
                "rain_flagged": bool(score.rain_flagged),
                "explanation": score.explanation,
            },
        }
        for score, zone in _ranked(db, city, None, city_code)
    ]
    return {"type": "FeatureCollection", "features": features}
