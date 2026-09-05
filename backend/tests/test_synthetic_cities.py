"""The synthetic city registry has to stay well-formed, because nothing else checks it.

A duplicate zone-id prefix does not raise -- it silently makes two cities fight over the
same primary keys, and the loader's insert either fails deep into a run or (with an
upsert) quietly overwrites one city with the other. That is the bug 656781c fixed once
already. These tests make the registry's invariants explicit instead of implied.
"""

import pytest

from pipelines.synthetic.cities import BY_CODE, BY_NAME, CITIES, ZONES_PER_TIER, get

# 28 states + 8 union territories. Pan-India has to mean pan-India, including the ones
# nobody remembers until someone from there is in the room.
EXPECTED_STATES_AND_UTS = 36


def test_codes_are_unique():
    assert len(BY_CODE) == len(CITIES)


def test_names_are_unique():
    assert len(BY_NAME) == len(CITIES)


def test_codes_are_url_and_csv_safe():
    """Zone ids end up in URLs, CSV exports and the map's tooltips.

    An accented or spaced code (a real hazard when city names come from a gazetteer --
    'Bhāgalpur', 'Port Blair') produces zone ids that need escaping everywhere they are
    used and break silently where they are not.
    """
    for city in CITIES:
        assert city.code.isalnum(), f"{city.name} has a non-alphanumeric code {city.code!r}"
        assert city.code.isascii(), f"{city.name} has a non-ASCII code {city.code!r}"
        assert city.code.isupper(), f"{city.name} has a lowercase code {city.code!r}"
        assert 1 <= len(city.code) <= 4, f"{city.name} has an odd-length code {city.code!r}"


def test_every_state_and_ut_is_covered():
    assert len({c.state for c in CITIES}) == EXPECTED_STATES_AND_UTS


def test_coordinates_are_inside_india():
    """A transposed lat/lon puts a city in the Indian Ocean and the map lands on water.

    This is a generous box around the country including the island territories, not a
    boundary test -- it only has to catch a swapped pair or a lost minus sign.
    """
    for city in CITIES:
        assert 6.0 <= city.lat <= 37.5, f"{city.name} latitude {city.lat} is outside India"
        assert 68.0 <= city.lon <= 97.5, f"{city.name} longitude {city.lon} is outside India"


def test_tiers_are_known():
    for city in CITIES:
        assert city.tier in ZONES_PER_TIER
        assert city.zone_count == ZONES_PER_TIER[city.tier]


def test_jaipur_stays_pinned():
    """Jaipur is the city the live dashboard has always shown.

    Its zones are Z-001..Z-030. Changing its code or its tier here silently replaces the
    one view the demo is built around -- which is exactly the regression that took the
    site down before. If this test fails, that is the change being caught, not a nuisance.
    """
    jaipur = get("Jaipur")
    assert jaipur.code == "Z"
    assert jaipur.zone_count == 30


def test_get_rejects_an_unknown_city_with_a_useful_message():
    with pytest.raises(KeyError, match="not in the synthetic city registry"):
        get("Atlantis")
