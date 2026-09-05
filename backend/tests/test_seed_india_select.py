"""Which cities a run will actually write. Owner: R1 (Satellite & Geo).

`--exclude` exists because of a deployment, not a hypothetical: production already holds a
real Jaipur, `--keep` does plain inserts, and a run that reaches a city already in the
database dies on its primary key. Getting the selection wrong either wipes real data or
crashes halfway, so it is tested away from the database.
"""

import pytest

from pipelines.synthetic.cities import CITIES
from pipelines.synthetic.seed_india import select_cities


def names(cities):
    return {c.name for c in cities}


def test_no_filters_selects_the_whole_registry():
    assert len(select_cities("", "", None)) == len(CITIES)


def test_exclude_drops_exactly_the_named_city():
    everything = select_cities("", "", None)
    without = select_cities("", "", None, exclude="Jaipur")
    assert names(everything) - names(without) == {"Jaipur"}


def test_exclude_takes_a_list():
    without = select_cities("", "", None, exclude="Jaipur, Pune ,Kohima")
    assert not names(without) & {"Jaipur", "Pune", "Kohima"}
    assert len(without) == len(CITIES) - 3


def test_a_misspelled_exclusion_is_loud():
    # The quiet failure this prevents: "Jaipurr" silently excluding nothing, the run
    # reaching the real Jaipur, and either crashing on its primary key or -- without
    # --keep -- having already wiped it.
    with pytest.raises(KeyError):
        select_cities("", "", None, exclude="Jaipurr")


def test_excluding_everything_stops_rather_than_seeding_nothing():
    every_name = ",".join(c.name for c in CITIES)
    with pytest.raises(SystemExit):
        select_cities("", "", None, exclude=every_name)


def test_exclude_applies_on_top_of_an_explicit_city_list():
    chosen = select_cities("Jaipur,Pune", "", None, exclude="Jaipur")
    assert names(chosen) == {"Pune"}


def test_exclude_runs_before_limit():
    # Otherwise --limit 3 --exclude <the largest> returns two cities, not three.
    chosen = select_cities("", "", 3, exclude=select_cities("", "", 1)[0].name)
    assert len(chosen) == 3
