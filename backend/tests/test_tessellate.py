"""Tests for the zone tessellation model. These are the invariants that would otherwise
only be caught by eyeballing a 7,000-polygon national build -- see the incident notes in
pipelines/geo/tessellate.py's docstring for the two real bugs this suite would have caught
(cross-city overlap, and population not being reduced when a neighbour wins territory).
"""

import pytest

from pipelines.geo.tessellate import (
    haversine_km,
    neighbours_within,
    service_radius_km,
    tessellate,
    zone_count,
    _cell_belongs_to,
)

JAIPUR = {"city_code": "JAI", "name": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873, "population": 3_046_163}
SMALL_TOWN = {"city_code": "TWN", "name": "Smalltown", "state": "Bihar", "lat": 25.0, "lon": 85.0, "population": 105_000}


def test_zone_count_grows_with_population_and_is_clamped():
    assert zone_count(100_000) >= 4
    assert zone_count(20_000_000) <= 120
    assert zone_count(3_000_000) > zone_count(150_000)


def test_service_radius_grows_with_population():
    assert service_radius_km(3_000_000) > service_radius_km(150_000) > 0


def test_tessellate_produces_unique_zone_ids_with_the_city_prefix():
    features = tessellate(JAIPUR)
    ids = [f["properties"]["zone_id"] for f in features]
    assert len(ids) == len(set(ids))
    assert all(zid.startswith("JAI-") for zid in ids)


def test_tessellate_zone_population_sums_to_the_city_population_when_unclipped():
    features = tessellate(JAIPUR)
    total = sum(f["properties"]["population"] for f in features)
    assert total == pytest.approx(JAIPUR["population"], rel=0.02)


def test_a_city_with_no_neighbours_keeps_its_whole_population():
    features = tessellate(SMALL_TOWN)
    assert all(f["properties"]["retention"] == 1.0 for f in features)


def test_a_hemmed_in_city_still_gets_at_least_one_zone():
    """Regression: a city so boxed in by larger neighbours it wins no lattice cell must
    still get its own centre zone -- real municipalities never score zero zones."""
    neighbour = {**JAIPUR, "city_code": "BIG", "population": 50_000_000}
    features = tessellate(SMALL_TOWN, neighbours=[neighbour])
    assert len(features) >= 1


def test_retention_reduces_population_when_a_neighbour_wins_territory():
    """Regression: before this was fixed, a clipped city kept its FULL population crammed
    into the few cells it won, producing an impossible population density.

    `_cell_belongs_to` is an unweighted nearest-centre test -- a cell is lost once it sits
    past the perpendicular bisector between the two centres, regardless of either city's
    population or service radius. So what clips a cell is the *distance between centres*
    relative to the small town's own radius (~2.2 km here), not the neighbour's size. This
    places the neighbour's centre well inside that radius so the bisector actually cuts
    through the small town's disc.
    """
    close_neighbour = {
        **JAIPUR,
        "city_code": "BIG",
        "lat": SMALL_TOWN["lat"] + 0.02,  # ~2.2 km -- inside the small town's own radius
        "lon": SMALL_TOWN["lon"],
        "population": 30_000_000,
    }
    gap = haversine_km(
        SMALL_TOWN["lat"], SMALL_TOWN["lon"], close_neighbour["lat"], close_neighbour["lon"]
    )
    assert gap < service_radius_km(SMALL_TOWN["population"]) * 2  # bisector falls inside our disc
    clipped = tessellate(SMALL_TOWN, neighbours=[close_neighbour])
    unclipped = tessellate(SMALL_TOWN)
    clipped_total = sum(f["properties"]["population"] for f in clipped)
    unclipped_total = sum(f["properties"]["population"] for f in unclipped)
    assert clipped_total < unclipped_total
    assert clipped[0]["properties"]["retention"] < 1.0


def test_cell_belongs_to_requires_every_corner_to_be_nearer():
    """Regression: a centre-only nearest-city test left ~3% of national zones overlapping
    a neighbour's. Corner-wise resolves it -- this is the geometric property that does."""
    neighbour = [{"lat": 26.92, "lon": 75.80}]
    # A cell whose corner pokes past the midpoint toward the neighbour must be rejected
    # even though its centre is on our side.
    assert not _cell_belongs_to(26.9124, 75.7873, 0.01, 0.02, 26.9124, 75.7873, neighbour)


def test_neighbours_within_finds_close_cities_and_excludes_itself():
    cities = [JAIPUR, {**JAIPUR, "city_code": "OTH", "name": "Other", "lat": 26.93, "lon": 75.80}]
    found = neighbours_within(JAIPUR, cities, radius_km=10)
    assert all(c["city_code"] != "JAI" for c in found)
    assert any(c["city_code"] == "OTH" for c in found)


def test_haversine_matches_known_distance_jaipur_to_delhi():
    km = haversine_km(26.9124, 75.7873, 28.6139, 77.2090)
    assert 225 <= km <= 245  # great-circle distance is ~235 km (road distance, ~270 km, is longer)
