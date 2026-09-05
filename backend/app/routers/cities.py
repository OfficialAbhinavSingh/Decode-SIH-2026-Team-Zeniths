"""Which cities have zones loaded. Owner: R3 (Backend & Fusion).

Read-only, and deliberately derived entirely from the `zones` and `zone_scores` tables
that already exist -- no new table, no new column, nothing to migrate. Whatever has been
loaded is what this lists, so it is correct for a database holding one seeded city and for
one holding the whole synthetic registry, with no code change between them.

The dashboard needs this to offer a city picker at all: before it existed the frontend had
no way to know that anything but CITY_DEFAULT was present.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Zone, ZoneScore
from ..schemas import CityOut

router = APIRouter(prefix="/api/cities", tags=["cities"])


@router.get("", response_model=list[CityOut])
def list_cities(db: Session = Depends(get_db)) -> list[dict]:
    """Every city with at least one zone, alphabetically.

    The centroid is the mean of the city's zone centroids, which is what the map needs to
    recentre when the picker changes -- and is exact enough for that, since the zones are
    a regular grid around the city centre in the first place.
    """
    rows = db.execute(
        select(
            Zone.city,
            func.count(Zone.id).label("zone_count"),
            func.avg(Zone.centroid_lat).label("lat"),
            func.avg(Zone.centroid_lon).label("lon"),
            # A LEFT join, not an inner one: a city whose zones are loaded but not yet
            # scored must still appear in the picker. An inner join would hide it and the
            # city would look missing rather than unscored.
            func.max(ZoneScore.fusion_score).label("top_score"),
        )
        .outerjoin(ZoneScore, ZoneScore.zone_id == Zone.id)
        .group_by(Zone.city)
        .order_by(Zone.city)
    ).all()

    return [
        {
            "city": row.city,
            "zone_count": row.zone_count,
            "centroid_lat": round(row.lat, 6),
            "centroid_lon": round(row.lon, 6),
            "top_score": round(row.top_score, 2) if row.top_score is not None else None,
        }
        for row in rows
    ]
