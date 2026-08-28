"""A report the intake already flagged as a duplicate must not score.

`routers/reports.py` runs the 200m/6hr spatial-temporal dedupe on every inbound report and
stamps `status = "duplicate"` on the ones it catches, logging "Dropped duplicate report" as
it does. Fusion then excluded only `dismissed`, so those rows were counted anyway and the
dedupe bought nothing at the point it actually mattered.

This was live, not hypothetical: production had 8 duplicate-flagged rows, all on one zone,
from a single person testing the Telegram bot. They saturated that zone's citizen score and
carried it to rank 6 of 30.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import BillingSignal, CitizenReport, SatelliteSignal, Zone, ZoneScore
from app.services.fusion import CITIZEN_SATURATION, run_fusion

CITY = "DupeReportTestCity"
ZONE_ID = "ZDUPE-001"


def _postgres_available() -> bool:
    try:
        with engine.connect():
            return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(not _postgres_available(), reason="no Postgres on DATABASE_URL")


def _wipe(session) -> None:
    """ZoneScore first: it carries the FK to zones, so deleting the zone fails otherwise."""
    for model in (ZoneScore, SatelliteSignal, BillingSignal, CitizenReport):
        session.query(model).filter_by(zone_id=ZONE_ID).delete()
    session.query(Zone).filter_by(id=ZONE_ID).delete()
    session.commit()


@pytest.fixture
def db():
    session = SessionLocal()
    _wipe(session)
    session.add(
        Zone(
            id=ZONE_ID,
            name="duplicate report test zone",
            city=CITY,
            centroid_lat=26.9,
            centroid_lon=75.8,
            geojson={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
        )
    )
    session.commit()
    yield session
    _wipe(session)
    session.close()


def _add_reports(db, statuses: list[str]) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    for i, status in enumerate(statuses):
        db.add(
            CitizenReport(
                zone_id=ZONE_ID,
                channel="telegram",
                description=f"report {i}",
                reported_at=now - dt.timedelta(hours=i),
                status=status,
            )
        )
    db.commit()


def _citizen_score(db) -> float | None:
    run_fusion(db, CITY)
    return db.scalars(select(ZoneScore).where(ZoneScore.zone_id == ZONE_ID)).one().citizen_score


@requires_pg
def test_duplicate_flagged_reports_do_not_score(db):
    """One genuine report plus four the dedupe caught is one report, not five."""
    _add_reports(db, ["new"] + ["duplicate"] * 4)
    assert _citizen_score(db) == pytest.approx(100.0 / CITIZEN_SATURATION)


@requires_pg
def test_a_zone_of_nothing_but_duplicates_has_no_citizen_signal(db):
    """Not a zero -- absent. A zone with no countable report has no citizen signal at all."""
    _add_reports(db, ["duplicate"] * 6)
    assert _citizen_score(db) is None


@requires_pg
def test_dismissed_reports_are_still_excluded(db):
    """The behaviour that already existed must survive the widened filter."""
    _add_reports(db, ["new", "dismissed"])
    assert _citizen_score(db) == pytest.approx(100.0 / CITIZEN_SATURATION)


@requires_pg
def test_genuine_reports_still_saturate(db):
    _add_reports(db, ["new"] * CITIZEN_SATURATION)
    assert _citizen_score(db) == pytest.approx(100.0)
