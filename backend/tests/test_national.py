"""The national view: one ranking over every city instead of one per city.

The endpoint exists because `zone_scores.fusion_score` is a within-city percentile, so the
obvious implementation -- select every row and sort by it -- puts one zone per city at
100.0 and orders the rest by nothing. Most of what is below is there to make sure that
mistake cannot come back in silently.
"""

import os
from types import SimpleNamespace

import pytest

from app.routers.national import _round_coords, rank_zones
from app.services.fusion import fuse


def pair(zone_id, city, *, sat=None, bill=None, cit=None, stored=100.0):
    """One (ZoneScore, Zone) row, with only the attributes rank_zones actually reads.

    `stored` is the within-city percentile already in the table. It is set to 100.0 by
    default on purpose: that is what every city's top zone really holds, and any ranking
    that reads it instead of recomputing will collapse.
    """
    score = SimpleNamespace(
        satellite_score=sat,
        billing_score=bill,
        citizen_score=cit,
        fusion_score=stored,
        confidence="high",
        signals_used=3,
        explanation="",
        computed_at=None,
    )
    zone = SimpleNamespace(id=zone_id, name=zone_id, city=city, ward=None, geojson={})
    return score, zone


def test_ranks_on_recomputed_magnitude_not_the_stored_percentile():
    # Two cities, both holding a stored 100.0 for their own worst zone. Ranked nationally,
    # the one actually leaking harder has to come first -- and the stored column cannot
    # tell you which that is.
    rows = rank_zones(
        [
            pair("A-001", "Amritsar", sat=30.0, bill=28.0, cit=20.0, stored=100.0),
            pair("B-001", "Bhopal", sat=95.0, bill=92.0, cit=90.0, stored=100.0),
        ]
    )
    assert [r["zone"].id for r in rows] == ["B-001", "A-001"]
    assert rows[0]["rank"] == 1
    assert rows[1]["rank"] == 2


def test_absolute_score_is_exactly_what_fuse_returns():
    rows = rank_zones([pair("A-001", "Agra", sat=80.0, bill=60.0, cit=None)])
    expected, _confidence, _used = fuse(80.0, 60.0, None)
    assert rows[0]["absolute_score"] == expected


def test_coverage_discount_still_applies_nationally():
    # A lone satellite reading of 95 must not outrank three corroborating signals at 80.
    # That is fusion.py's COVERAGE_FACTOR doing its job, and the national view gets it for
    # free only because it calls fuse() rather than restating the arithmetic.
    rows = rank_zones(
        [
            pair("SOLO-001", "Solapur", sat=95.0),
            pair("TRIO-001", "Thrissur", sat=80.0, bill=80.0, cit=80.0),
        ]
    )
    assert [r["zone"].id for r in rows] == ["TRIO-001", "SOLO-001"]


def test_percentile_uses_the_full_range_across_the_country():
    rows = rank_zones(
        [
            pair("A-001", "Ajmer", sat=10.0, bill=10.0, cit=10.0),
            pair("B-001", "Bhuj", sat=50.0, bill=50.0, cit=50.0),
            pair("C-001", "Cuttack", sat=90.0, bill=90.0, cit=90.0),
        ]
    )
    assert rows[0]["fusion_score"] == 100.0
    assert rows[-1]["fusion_score"] == 0.0


def test_ranks_are_contiguous_and_start_at_one():
    rows = rank_zones([pair(f"Z-{i:03d}", "Zirakpur", sat=float(i)) for i in range(1, 26)])
    assert [r["rank"] for r in rows] == list(range(1, 26))


def test_identical_evidence_ranks_in_a_fixed_order():
    # Two zones on the same numbers must not swap places between requests, or the "rank #4"
    # a crew was handed this morning means a different zone this afternoon.
    args = dict(sat=70.0, bill=70.0, cit=70.0)
    first = rank_zones([pair("B-002", "B", **args), pair("A-001", "A", **args)])
    second = rank_zones([pair("A-001", "A", **args), pair("B-002", "B", **args)])
    assert [r["zone"].id for r in first] == [r["zone"].id for r in second] == ["A-001", "B-002"]


def test_the_displayed_score_never_disagrees_with_the_rank():
    # Ties are where these two can come apart: percentile_rank() splits equal values, so a
    # careless ordering can hand rank #1 a smaller number than rank #2 and the list reads as
    # if it were sorted wrong. Half of these zones are deliberately identical.
    rows = rank_zones(
        [pair(f"Z-{i:03d}", "Z", sat=float(i // 2)) for i in range(1, 21)]
    )
    scores = [r["fusion_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert [r["rank"] for r in rows] == list(range(1, 21))


def test_a_zone_with_no_signals_at_all_ranks_last_rather_than_crashing():
    rows = rank_zones([pair("EMPTY-001", "E"), pair("FULL-001", "F", sat=50.0)])
    assert rows[-1]["zone"].id == "EMPTY-001"
    assert rows[-1]["absolute_score"] == 0.0


def test_round_coords_walks_every_nesting_depth():
    polygon = [[[75.1234567, 26.7654321], [75.2345678, 26.8765432]]]
    assert _round_coords(polygon) == [[[75.12346, 26.76543], [75.23457, 26.87654]]]
    # MultiPolygon is one ring deeper, and a non-numeric leaf must survive untouched.
    assert _round_coords([[[[1.111111, 2.222222]]]]) == [[[[1.11111, 2.22222]]]]
    assert _round_coords("Polygon") == "Polygon"


# ------------------------------------------------------------------ against a database

pytestmark_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs a database to query"
)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytestmark_db
def test_geojson_covers_every_scored_zone(client):
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import ZoneScore

    body = client.get("/api/national/geojson").json()
    with SessionLocal() as db:
        scored = db.scalar(select(func.count(ZoneScore.zone_id)))

    assert body["type"] == "FeatureCollection"
    assert body["zone_count"] == len(body["features"]) == scored


@pytestmark_db
def test_properties_carry_everything_the_evidence_panel_needs(client):
    # The frontend builds its ranked list from these properties rather than from a second
    # request, so a missing key here is a zone the map can show and the panel cannot open.
    needed = {
        "zone_id",
        "name",
        "city",
        "rank",
        "fusion_score",
        "absolute_score",
        "confidence",
        "signals_used",
        "satellite_score",
        "billing_score",
        "citizen_score",
        "explanation",
    }
    body = client.get("/api/national/geojson").json()
    for feature in body["features"][:50]:
        assert needed <= set(feature["properties"])
        assert 0 <= feature["properties"]["fusion_score"] <= 100


@pytestmark_db
def test_the_city_endpoints_are_unaffected(client):
    # The national view is additive. /api/scores still percentile-ranks within one city,
    # which is why its top zone is still exactly 100 while the same zone's national score
    # is whatever the rest of the country says it is.
    rows = client.get("/api/scores?limit=5").json()
    if rows:
        assert rows[0]["rank"] == 1
        assert rows[0]["fusion_score"] == 100.0
