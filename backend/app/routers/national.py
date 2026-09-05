"""National coverage endpoints -- the zoomed-out half of the dashboard.

Owner: R3 (Backend & Fusion), added for pan-India coverage.

WHY THESE EXIST AND `/api/scores/geojson` DOES NOT SUFFICE: that endpoint returns every
scored polygon for a city, which is right at city zoom and impossible at country zoom --
7,000 polygons is roughly 3 MB of GeoJSON and several seconds of Leaflet layout on a
judge's phone. The map therefore has three levels of detail, and each has its own
endpoint that returns only what that zoom can actually show:

    country  ->  GET /api/national/states    36 rows, one per state
    country  ->  GET /api/national/cities    ~510 points, one per city
    city     ->  GET /api/scores/geojson     that city's polygons only

Level of detail is a data decision, not a rendering one: the wrong shape of response
cannot be fixed in the client.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import City, CityScore, GroundwaterStress, Zone, ZoneScore
from ..services import impact

router = APIRouter(prefix="/api/national", tags=["national"])


@router.get("/summary")
def national_summary(db: Session = Depends(get_db)) -> dict:
    """One object with everything the header strip shows. Cheap, aggregate-only."""
    cities = db.execute(
        select(
            func.count(CityScore.id),
            func.sum(CityScore.zones_scored),
            func.sum(CityScore.water_at_risk_kld),
            func.sum(CityScore.population_served),
            func.sum(CityScore.high_priority_zones),
        )
    ).one()
    count, zones, water, population, high = cities
    water = float(water or 0.0)

    registered = db.scalar(select(func.count(City.code))) or 0
    total_zones = db.scalar(select(func.count(Zone.id))) or 0
    states = db.scalar(select(func.count(func.distinct(City.state)))) or 0

    return {
        "cities_registered": registered,
        "cities_scored": int(count or 0),
        "zones_total": total_zones,
        "zones_scored": int(zones or 0),
        "states_covered": states,
        "population_covered": int(population or 0),
        "high_priority_zones": int(high or 0),
        "water_at_risk_kld": round(water, 2),
        "annual_value_inr": impact.annual_value_inr(water),
        "households_served": impact.households_served(water),
        "assumptions": impact.ASSUMPTIONS,
    }


@router.get("/states")
def state_rollup(db: Session = Depends(get_db)) -> list[dict]:
    """One row per state: the choropleth at country zoom.

    Ranked by the worst city in the state rather than the state's mean, for the same
    reason the city ranking uses its worst zone -- a mean over 40 cities hides the one
    that needs a crew.
    """
    rows = db.execute(
        select(
            CityScore.state,
            func.count(CityScore.id),
            func.sum(CityScore.zones_scored),
            func.max(CityScore.max_priority),
            func.avg(CityScore.mean_priority),
            func.sum(CityScore.water_at_risk_kld),
            func.sum(CityScore.population_served),
            func.sum(CityScore.high_priority_zones),
        ).group_by(CityScore.state)
    ).all()

    stress = {
        s.state.strip().casefold(): s
        for s in db.scalars(select(GroundwaterStress).where(GroundwaterStress.district.is_(None)))
    }

    out = []
    for state, cities, zones, worst, mean, water, population, high in rows:
        gw = stress.get((state or "").strip().casefold())
        out.append(
            {
                "state": state,
                "cities": int(cities or 0),
                "zones_scored": int(zones or 0),
                "max_priority": round(float(worst or 0), 2),
                "mean_priority": round(float(mean or 0), 2),
                "high_priority_zones": int(high or 0),
                "water_at_risk_kld": round(float(water or 0), 2),
                "population_covered": int(population or 0),
                "groundwater_stress_pct": gw.stage_of_extraction_pct if gw else None,
                "groundwater_category": gw.category if gw else None,
            }
        )
    out.sort(key=lambda r: r["max_priority"], reverse=True)
    return out


@router.get("/cities")
def city_rollup(
    state: str | None = Query(default=None),
    limit: int = Query(default=600, ge=1, le=2000),
    min_priority: float = Query(default=0.0, ge=0, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """One point per city: the bubble layer between country and city zoom."""
    stmt = (
        select(CityScore, City)
        .join(City, CityScore.city_code == City.code)
        .where(CityScore.max_priority >= min_priority)
        .order_by(CityScore.rank)
        .limit(limit)
    )
    if state:
        stmt = stmt.where(CityScore.state == state)

    return [
        {
            "city_code": score.city_code,
            "city": score.city,
            "state": score.state,
            "lat": city.lat,
            "lon": city.lon,
            "population": city.population,
            "rank": score.rank,
            "zones_scored": score.zones_scored,
            "max_priority": score.max_priority,
            "mean_priority": score.mean_priority,
            "high_priority_zones": score.high_priority_zones,
            "hotspot_zone_id": score.hotspot_zone_id,
            "groundwater_stress_pct": score.groundwater_stress_pct,
            "water_at_risk_kld": score.water_at_risk_kld,
            "annual_value_inr": impact.annual_value_inr(score.water_at_risk_kld or 0),
            "population_served": score.population_served,
            "computed_at": score.computed_at,
        }
        for score, city in db.execute(stmt).all()
    ]


@router.get("/cities/{city_code}")
def city_detail(city_code: str, db: Session = Depends(get_db)) -> dict:
    """A single city plus its worst zones -- what the drill-down panel opens with."""
    city = db.get(City, city_code)
    if city is None:
        raise HTTPException(status_code=404, detail=f"city {city_code} not found")

    score = db.scalars(select(CityScore).where(CityScore.city_code == city_code)).first()
    worst = db.execute(
        select(ZoneScore, Zone)
        .join(Zone, ZoneScore.zone_id == Zone.id)
        .where(Zone.city_code == city_code)
        .order_by(ZoneScore.priority_score.desc())
        .limit(10)
    ).all()

    return {
        "city_code": city.code,
        "city": city.name,
        "state": city.state,
        "lat": city.lat,
        "lon": city.lon,
        "population": city.population,
        "zone_count": city.zone_count,
        "service_radius_km": city.service_radius_km,
        "area_km2": city.area_km2,
        "pipe_length_km": city.pipe_length_km,
        "rank": score.rank if score else None,
        "max_priority": score.max_priority if score else None,
        "mean_priority": score.mean_priority if score else None,
        "water_at_risk_kld": score.water_at_risk_kld if score else None,
        "annual_value_inr": impact.annual_value_inr(score.water_at_risk_kld or 0) if score else None,
        "groundwater_stress_pct": score.groundwater_stress_pct if score else None,
        "worst_zones": [
            {
                "zone_id": zs.zone_id,
                "name": zone.name,
                "rank": zs.rank,
                "priority_score": zs.priority_score,
                "fusion_score": zs.fusion_score,
                "confidence": zs.confidence,
                "signals_used": zs.signals_used,
                "water_at_risk_kld": zs.water_at_risk_kld,
                "explanation": zs.explanation,
            }
            for zs, zone in worst
        ],
    }
