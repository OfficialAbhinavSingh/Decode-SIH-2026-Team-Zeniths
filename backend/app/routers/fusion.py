from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import FusionResult
from ..services.fusion import run_fusion

router = APIRouter(prefix="/api/fusion", tags=["fusion"])


@router.post("/run", response_model=FusionResult)
def run(city: str = Query(default=None), db: Session = Depends(get_db)) -> dict:
    """Recompute every zone's priority score. Safe to call as often as you like."""
    city = city or settings.city_default
    count = run_fusion(db, city)
    return {"zones_scored": count, "city": city}
