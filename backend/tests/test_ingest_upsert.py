"""Ingest upsert path.

The pure parts run anywhere. The database parts need a live Postgres and are skipped
when there isn't one -- CI runs the test suite without a database on purpose. To run
them: `docker compose up -d db && python -m app.init_db && python -m pytest tests/ -q`.
"""

import datetime as dt

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.db import SessionLocal, engine
from app.models import SatelliteSignal, Zone
from app.routers.ingest import _dedupe, _upsert

DAY = dt.date(2026, 8, 25)
ZONE_ID = "ZTEST-001"
SAT_KEY = ["zone_id", "observed_on"]


def _row(score: float, day: dt.date = DAY) -> dict:
    return {
        "zone_id": ZONE_ID,
        "observed_on": day,
        "ndvi_mean": 0.4,
        "ndvi_baseline": 0.3,
        "ndvi_anomaly": 0.11,
        "wetness_index": 0.44,
        "cloud_pct": 7.2,
        "score": score,
        "source": "test",
    }


def _postgres_available() -> bool:
    try:
        with engine.connect():
            return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(not _postgres_available(), reason="no Postgres on DATABASE_URL")


# --- pure ---------------------------------------------------------------------------


def test_dedupe_keeps_last_row_for_a_repeated_key():
    rows = _dedupe([_row(55.0), _row(66.0)], SAT_KEY)
    assert len(rows) == 1
    assert rows[0]["score"] == 66.0


def test_dedupe_keeps_distinct_keys():
    rows = _dedupe([_row(55.0), _row(66.0, dt.date(2026, 8, 26))], SAT_KEY)
    assert len(rows) == 2


def test_dedupe_preserves_first_appearance_order():
    a, b = _row(1.0, dt.date(2026, 8, 24)), _row(2.0)
    assert [r["observed_on"] for r in _dedupe([a, b, a], SAT_KEY)] == [a["observed_on"], DAY]


# --- against a real database --------------------------------------------------------


@pytest.fixture
def db():
    session = SessionLocal()
    session.merge(
        Zone(
            id=ZONE_ID,
            name="upsert test zone",
            city="TestCity",
            centroid_lat=26.9,
            centroid_lon=75.8,
            geojson={},
        )
    )
    session.commit()
    yield session
    session.query(SatelliteSignal).filter_by(zone_id=ZONE_ID).delete()
    session.query(Zone).filter_by(id=ZONE_ID).delete()
    session.commit()
    session.close()


def _stored(db):
    return db.execute(
        select(func.count(), func.max(SatelliteSignal.score)).where(
            SatelliteSignal.zone_id == ZONE_ID
        )
    ).one()


@requires_pg
def test_reingesting_the_same_day_overwrites_instead_of_duplicating(db):
    assert _upsert(db, SatelliteSignal, [_row(55.0)], SAT_KEY) == 1
    assert _upsert(db, SatelliteSignal, [_row(72.0)], SAT_KEY) == 1
    count, score = _stored(db)
    assert (count, score) == (1, 72.0)


@requires_pg
def test_duplicate_keys_in_one_batch_do_not_blow_up(db):
    # Postgres raises CardinalityViolation on a batch that hits one key twice. A CSV that
    # got concatenated or re-exported does exactly that, so the endpoint must survive it.
    assert _upsert(db, SatelliteSignal, [_row(55.0), _row(66.0)], SAT_KEY) == 1
    count, score = _stored(db)
    assert (count, score) == (1, 66.0)


@requires_pg
def test_empty_batch_is_a_no_op(db):
    assert _upsert(db, SatelliteSignal, [], SAT_KEY) == 0
    assert _stored(db)[0] == 0


@requires_pg
def test_missing_constraint_reports_the_actual_fix(db):
    # A database created before the natural-key constraints existed. Postgres calls this an
    # InvalidColumnReference, which tells nobody what to do -- we translate it.
    with pytest.raises(HTTPException) as exc:
        _upsert(db, SatelliteSignal, [_row(55.0)], ["zone_id", "score"])
    assert "python -m app.init_db" in exc.value.detail
