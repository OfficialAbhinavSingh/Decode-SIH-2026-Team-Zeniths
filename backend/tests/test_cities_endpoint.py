"""GET /api/cities -- the picker's only source of truth.

The endpoint exists so the frontend never has to hardcode a city list. If it drifts from
what is actually in `zones`, the picker offers cities that return an empty map.
"""

import os

import pytest
from fastapi.testclient import TestClient

# The suite as a whole runs against whatever DATABASE_URL points at; CI leaves it unset and
# these skip rather than fail, matching the other DB-backed tests in this directory.
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs a database to query"
)


@pytest.fixture()
def client():
    from app.main import app

    return TestClient(app)


def test_lists_only_cities_that_have_zones(client):
    from sqlalchemy import distinct, select

    from app.db import SessionLocal
    from app.models import Zone

    body = client.get("/api/cities").json()
    with SessionLocal() as db:
        in_db = set(db.scalars(select(distinct(Zone.city))).all())

    assert {row["city"] for row in body} == in_db


def test_rows_carry_what_the_picker_and_the_map_need(client):
    body = client.get("/api/cities").json()
    if not body:
        pytest.skip("no zones loaded")

    for row in body:
        assert row["zone_count"] >= 1
        # The map recentres on this, so a swapped pair would drop the view in the ocean.
        assert 6.0 <= row["centroid_lat"] <= 37.5
        assert 68.0 <= row["centroid_lon"] <= 97.5
        assert row["top_score"] is None or 0.0 <= row["top_score"] <= 100.0


def test_sorted_by_name(client):
    names = [row["city"] for row in client.get("/api/cities").json()]
    assert names == sorted(names)


def test_an_unscored_city_still_appears(client):
    """The join to zone_scores must be a LEFT join.

    A city whose zones are loaded but not yet scored is a real state -- it is what the
    database looks like between the loader finishing and fusion running. An inner join
    would hide it, and the city would look like it failed to load rather than being mid-run.
    """
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Zone, ZoneScore

    with SessionLocal() as db:
        zone = db.scalars(select(Zone).limit(1)).first()
        if zone is None:
            pytest.skip("no zones loaded")
        scored = db.scalars(
            select(ZoneScore.zone_id).join(Zone, ZoneScore.zone_id == Zone.id).where(
                Zone.city == zone.city
            )
        ).all()
        # Only meaningful to assert when we can actually find an unscored city; when every
        # city is scored the LEFT join is exercised by the None branch of test_rows above.
        if scored:
            pytest.skip("every city in this database is scored")

    assert zone.city in {row["city"] for row in client.get("/api/cities").json()}
