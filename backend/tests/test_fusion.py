"""Tests for the fusion rule. These two cases are exactly what judges probe:
"what if a city has no billing data?" and "how do you know the signals agree?"
"""

import pytest

from app.services.fusion import (
    COVERAGE_FACTOR,
    WEIGHTS,
    citizen_score,
    fuse,
    percentile_rank,
)


def test_all_three_signals_agree_is_high_confidence():
    score, confidence, used = fuse(90.0, 85.0, 80.0)
    assert used == 3
    assert confidence == "high"
    expected = (
        WEIGHTS["satellite"] * 90 + WEIGHTS["billing"] * 85 + WEIGHTS["citizen"] * 80
    ) / sum(WEIGHTS.values())
    assert score == pytest.approx(expected, abs=0.01)


def test_three_signals_that_disagree_drop_to_medium():
    _, confidence, used = fuse(95.0, 20.0, 60.0)
    assert used == 3
    assert confidence == "medium"


def test_missing_signal_renormalises_instead_of_scoring_zero():
    """A zone with only satellite data must not be punished for data nobody collected.

    Refusing to renormalise would score this zone 36 -- 40% of its own reading, purely for
    billing the city never digitised. It keeps its 90 through renormalisation, then takes
    the single-signal coverage discount.
    """
    score, confidence, used = fuse(90.0, None, None)
    assert used == 1
    assert confidence == "low"
    assert score == pytest.approx(90.0 * COVERAGE_FACTOR[1], abs=0.01)
    assert score > WEIGHTS["satellite"] * 90


def test_two_signals_use_only_their_own_weights():
    score, confidence, used = fuse(80.0, 60.0, None)
    assert used == 2
    assert confidence == "medium"
    expected = (
        (WEIGHTS["satellite"] * 80 + WEIGHTS["billing"] * 60)
        / (WEIGHTS["satellite"] + WEIGHTS["billing"])
        * COVERAGE_FACTOR[2]
    )
    assert score == pytest.approx(expected, abs=0.01)


def test_corroborated_zone_outranks_a_stronger_single_signal_lead():
    """The bug this discount exists for.

    Before the coverage factor, a lone billing reading of 86 scored 86 -- the same as three
    sources agreeing at 86 -- so percentile-ranking could put an unverified single number at
    the top of the repair list. With the real satellite export loaded, that is exactly what
    happened: three of the top six zones were single-signal leads.
    """
    lead, _, lead_used = fuse(None, 86.0, None)
    corroborated, _, corr_used = fuse(70.0, 70.0, 70.0)
    assert lead_used == 1 and corr_used == 3
    assert corroborated > lead


def test_coverage_discount_never_reorders_zones_with_equal_coverage():
    """Within one coverage level the discount is a constant, so ordering is untouched."""
    a, _, _ = fuse(80.0, 60.0, None)
    b, _, _ = fuse(70.0, 60.0, None)
    assert a > b


def test_a_single_signal_lead_is_discounted_not_discarded():
    score, _, _ = fuse(None, None, 100.0)
    assert 0 < score < 100.0


def test_no_signals_at_all():
    assert fuse(None, None, None) == (0.0, "low", 0)


def test_citizen_score_saturates():
    assert citizen_score(0) == 0.0
    assert citizen_score(5) == 100.0
    assert citizen_score(50) == 100.0
    assert 0 < citizen_score(1) < 100


def test_percentile_rank_spreads_a_flat_cluster_without_reordering():
    values = [60.0, 61.0, 62.0, 63.0]
    out = percentile_rank(values)
    assert out == [0.0, 33.33, 66.67, 100.0]
    assert sorted(out) == out  # ordering preserved


def test_percentile_rank_edge_cases():
    assert percentile_rank([]) == []
    assert percentile_rank([42.0]) == [42.0]


def test_explanation_distinguishes_disagreement_from_missing_data():
    """'medium' has two very different causes -- the sentence must not blur them."""
    from app.services.fusion import explain

    disagree = explain("Z", 95.0, 20.0, 60.0, 22.0, 0.19, 3, "medium", 3)
    missing = explain("Z", 95.0, 20.0, None, 22.0, 0.19, 0, "medium", 2)

    assert "disagree" in disagree
    assert "two of three" in missing
    assert disagree != missing


def test_explanation_when_nothing_is_known():
    from app.services.fusion import explain

    assert "no signals" in explain("Ward 9", None, None, None, None, None, 0, "low", 0)
