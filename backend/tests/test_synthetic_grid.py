"""The seeded generator has to be reproducible, and it has to keep the Jaipur format.

"Seeded" is the whole feature: if the grid moves between runs, a screenshot stops matching
the map, two teammates see different top-ranked zones, and nothing about the demo is
defensible. These tests pin that down, and pin the two places where drift would be silent
rather than loud.
"""

import random
from datetime import date

from pipelines.synthetic import grid
from pipelines.synthetic.cities import CITIES, get
from seed import CELL as SEED_CELL
from seed import billing_period as seed_billing_period
from seed import build_zones as seed_build_zones


def test_the_same_city_generates_identical_zones_every_time():
    a = grid.build_zones(get("Pune"))
    b = grid.build_zones(get("Pune"))
    assert a == b


def test_the_seed_does_not_depend_on_the_process():
    """A hardcoded expectation, because that is the only thing that catches hash() creeping
    back in: Python salts str hashing per process, so a hash()-based seed passes an
    equality test inside one run and gives a different city on the next."""
    assert grid.city_seed("Jaipur") == grid.city_seed("Jaipur")
    assert grid.city_seed("Jaipur") != grid.city_seed("Jodhpur")
    # Pinned literal, the first 8 bytes of sha256("Jaipur"). An equality-to-itself check
    # would pass under hash() too; only a fixed expected value catches the swap.
    assert grid.city_seed("Jaipur") == 9535520295357455660


def test_cities_do_not_share_a_random_stream():
    """Adding or reordering a city must not move another city's numbers.

    seed.py draws every value in one city from a single module-level Random, and its own
    comments explain the trap that creates. Per-city streams are what make the registry
    safe to edit.
    """
    before = grid.build_zones(get("Kochi"))
    # Generate an unrelated city in between -- with a shared stream this would shift Kochi.
    grid.build_city(get("Ludhiana"))
    assert grid.build_zones(get("Kochi")) == before


def test_zone_ids_are_unique_across_the_whole_registry():
    """`zones.id` is one global primary key, not one per city."""
    seen: dict[str, str] = {}
    for city in CITIES:
        for zone in grid.build_zones(city):
            clash = seen.get(zone["id"])
            assert clash is None, f"{zone['id']} generated for both {clash} and {city.name}"
            seen[zone["id"]] = city.name


def test_jaipur_reproduces_the_original_seed_grid_exactly():
    """The generator must be a strict generalisation of seed.py, not a replacement.

    Same ids, same ward/sector names, same centroids, same polygons. Given the same random
    stream it also draws the same pipe lengths and populations -- so passing seed.py's
    Random(2026) here reproduces `python seed.py` output row for row. That is the guarantee
    that turning on national data does not disturb the city the demo runs on.
    """
    expected = seed_build_zones("Jaipur", 30)
    actual = grid.build_zones(get("Jaipur"), random.Random(2026))

    assert len(actual) == len(expected) == 30
    for got, want in zip(actual, expected, strict=True):
        assert got["id"] == want.id
        assert got["name"] == want.name
        assert got["city"] == want.city
        assert got["ward"] == want.ward
        assert got["centroid_lat"] == want.centroid_lat
        assert got["centroid_lon"] == want.centroid_lon
        assert got["geojson"] == want.geojson
        assert got["pipe_length_km"] == want.pipe_length_km
        assert got["population"] == want.population


def test_cell_size_matches_the_rest_of_the_project():
    """seed.py, build_city_zones.py and this module all tile at the same resolution.

    Zones of different sizes are not comparable, and fusion percentile-ranks them against
    each other as though they were.
    """
    assert grid.CELL == SEED_CELL


def test_billing_period_matches_seed_and_the_real_pipeline():
    """BillingSignal's natural key includes the period.

    If this module's window drifts from seed.py's, R2's real ingest no longer upserts over
    the synthetic row -- both survive, and fusion's "latest period_end" lookup can keep
    serving the fabricated one indefinitely. That failure is completely silent.
    """
    for today in (date(2026, 1, 1), date(2026, 3, 15), date(2026, 12, 31)):
        assert grid.billing_period(today) == seed_billing_period(today)


def test_signals_cover_every_zone_and_stay_in_range():
    zones, signals = grid.build_city(get("Guwahati"))
    assert {s["zone_id"] for s in signals["satellite"]} == {z["id"] for z in zones}
    assert {b["zone_id"] for b in signals["billing"]} == {z["id"] for z in zones}

    for row in signals["satellite"]:
        assert 0.0 <= row["score"] <= 100.0
        assert row["source"] == "seed", "must lose to real Sentinel-2 data in fusion"
    for row in signals["billing"]:
        assert 0.0 <= row["nrw_pct"] <= 100.0
        assert 0.0 <= row["score"] <= 100.0
        assert row["billed_kl"] <= row["supplied_kl"]
        assert row["is_synthetic"] is True, "synthetic data must be labelled as such"


def test_citizen_reports_land_inside_their_own_zone():
    """R5 matches a report to a zone by point-in-polygon.

    A report scattered outside its cell would be matched to a neighbour or to nothing,
    so the seeded jitter has to stay within the cell it belongs to.
    """
    zones, signals = grid.build_city(get("Bhopal"))
    by_id = {z["id"]: z for z in zones}
    half = grid.CELL / 2
    for report in signals["citizen"]:
        zone = by_id[report["zone_id"]]
        assert abs(report["lat"] - zone["centroid_lat"]) < half
        assert abs(report["lon"] - zone["centroid_lon"]) < half


def test_every_city_plants_at_least_one_hotspot():
    """A city with no planted leak ranks 30 near-identical zones and the map is flat --
    technically fine, and useless to demo."""
    for city in CITIES:
        zones = grid.build_zones(city)
        hotspots = grid.pick_hotspots(zones, grid.rng_for(city))
        assert hotspots, f"{city.name} has no hotspot"
        assert len(hotspots) <= len(zones)


def test_grid_is_roughly_square_for_every_tier():
    for count in (18, 30, 40, 60):
        cols = grid.grid_cols(count)
        rows = count / cols
        assert 0.5 <= rows / cols <= 1.2, f"{count} zones tiles as {cols} cols x {rows} rows"
