from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import FusionResult
from ..services.fusion import run_fusion, run_national_fusion

router = APIRouter(prefix="/api/fusion", tags=["fusion"])


@router.post("/run", response_model=FusionResult)
def run(city: str = Query(default=None), db: Session = Depends(get_db)) -> dict:
    """Recompute every zone's priority score. Safe to call as often as you like."""
    city = city or settings.city_default
    count = run_fusion(db, city)
    return {"zones_scored": count, "city": city}


@router.post("/run/national")
def run_national(
    limit_cities: int | None = Query(default=None, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    """Recompute every zone in the country and re-rank the cities against each other.

    One pass over the whole database rather than 500 calls to `/run` -- the signal
    lookups are shared, which is the difference between seconds and minutes. `limit_cities`
    scores only the N largest, for a fast smoke test against a full national load.
    """
    return run_national_fusion(db, limit_cities)
