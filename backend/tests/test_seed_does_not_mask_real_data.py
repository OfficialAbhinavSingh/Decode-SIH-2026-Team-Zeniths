"""Seeded demo data must never outrank real ingested data.

`python seed.py` is not just a dev convenience -- the offline demo fallback runs it, and
so does every teammate's local setup. If a seeded row wins the "latest signal per zone"
lookup in fusion, the dashboard shows fabricated figures while real satellite and billing
data sit in the database being ignored. That failure is silent: ingest reports success,
the map just quietly shows the wrong numbers.

Both regressions below were live bugs, not hypotheticals.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import BillingSignal, SatelliteSignal, Zone, ZoneScore
from app.services.fusion import run_fusion
from seed import billing_period

CITY = "SeedMaskTestCity"
ZONE_ID = "ZMASK-001"


def _postgres_available() -> bool:
    try:
        with engine.connect():
            return True
    except Exception:
        return False


requires_pg = pytest.mark.skipif(not _postgres_available(), reason="no Postgres on DATABASE_URL")


# --- pure -----------------------------------------------------------------------------


def test_seed_billing_period_matches_the_generator_convention():
    """seed.py and pipelines/billing/generate.py must produce the same period.

    BillingSignal's natural key is (zone_id, period_start, period_end). If these two
    disagree, the real pipeline inserts a *second* row instead of upserting over the
    seeded one, and whichever has the later period_end wins fusion -- which was the seed
    row, always, because its window was rolling and the generator's is a calendar month.
    """
    today = dt.date(2026, 8, 27)

    # generate.py's convention, replicated here on purpose: this test is the tripwire for
    # the two files drifting apart, so it must not import the value it is checking.
    expected_end = today.replace(day=1) - dt.timedelta(days=1)
    expected_start = expected_end.replace(day=1)

    assert billing_period(today) == (expected_start, expected_end)
    assert billing_period(today) == (dt.date(2026, 7, 1), dt.date(2026, 7, 31))


def test_billing_period_is_a_full_month_at_a_month_boundary():
    """1st of the month is the edge case: yesterday was the last day of the prior month."""
    assert billing_period(dt.date(2026, 9, 1)) == (dt.date(2026, 8, 1), dt.date(2026, 8, 31))
    assert billing_period(dt.date(2026, 1, 1)) == (dt.date(2025, 12, 1), dt.date(2025, 12, 31))


# --- against a real database ----------------------------------------------------------


def _wipe(session) -> None:
    """ZoneScore first: it carries the FK to zones, so deleting the zone fails otherwise."""
    for model in (ZoneScore, SatelliteSignal, BillingSignal):
        session.query(model).filter_by(zone_id=ZONE_ID).delete()
    session.query(Zone).filter_by(id=ZONE_ID).delete()
    session.commit()


@pytest.fixture
def db():
    session = SessionLocal()
    _wipe(session)  # also clears anything a previously failed run left behind
    session.add(
        Zone(
            id=ZONE_ID,
            name="seed masking test zone",
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


def _fusion_scores(db):
    run_fusion(db, CITY)
    return db.scalars(select(ZoneScore).where(ZoneScore.zone_id == ZONE_ID)).one()


@requires_pg
def test_real_satellite_beats_a_seed_row_with_a_later_date(db):
    """seed.py stamps observed_on = today-3d, which is newer than most real GEE exports."""
    real_day = dt.date(2026, 8, 25)
    seed_day = real_day + dt.timedelta(days=5)  # seeded data is "fresher" by date

    db.add(
        SatelliteSignal(
            zone_id=ZONE_ID,
            observed_on=real_day,
            ndvi_mean=0.40,
            ndvi_baseline=0.30,
            ndvi_anomaly=0.10,
            score=88.0,
            source="sentinel2-gee",
        )
    )
    db.add(
        SatelliteSignal(
            zone_id=ZONE_ID,
            observed_on=seed_day,
            ndvi_mean=0.31,
            ndvi_baseline=0.30,
            ndvi_anomaly=0.01,
            score=4.0,
            source="seed",
        )
    )
    db.commit()

    assert _fusion_scores(db).satellite_score == 88.0


@requires_pg
def test_seed_row_is_still_used_when_it_is_the_only_data(db):
    """The offline fallback depends on this: no real data means seeded data must show."""
    db.add(
        SatelliteSignal(
            zone_id=ZONE_ID,
            observed_on=dt.date(2026, 8, 24),
            ndvi_mean=0.45,
            ndvi_baseline=0.30,
            ndvi_anomaly=0.15,
            score=67.0,
            source="seed",
        )
    )
    db.commit()

    assert _fusion_scores(db).satellite_score == 67.0


@requires_pg
def test_real_billing_upserts_over_the_seeded_row_instead_of_competing(db):
    """Same natural key => one row. This is what the period alignment buys us."""
    start, end = billing_period()

    seeded = BillingSignal(
        zone_id=ZONE_ID,
        period_start=start,
        period_end=end,
        supplied_kl=20_000.0,
        billed_kl=17_480.0,
        nrw_pct=12.6,
        score=21.0,
        is_synthetic=True,
    )
    db.add(seeded)
    db.commit()

    # R2's pipeline ingests the real figures for the same period.
    seeded.supplied_kl = 27_310.1
    seeded.billed_kl = 11_813.7
    seeded.nrw_pct = 56.74
    seeded.score = 96.55
    db.commit()

    stored = db.scalars(select(BillingSignal).where(BillingSignal.zone_id == ZONE_ID)).all()
    assert len(stored) == 1, "seed and real rows must collapse to one via the natural key"
    assert _fusion_scores(db).billing_score == 96.55
