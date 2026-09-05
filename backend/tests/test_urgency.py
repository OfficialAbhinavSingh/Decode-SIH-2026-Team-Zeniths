"""Tests for the groundwater urgency lift. See app/services/urgency.py for the argument
for why this is additive headroom, not a multiplier, and why that matters for ranking.
"""

import pytest

from app.services.urgency import apply_urgency, categorise, effective_multiplier, urgency_boost


def test_safe_band_has_no_effect():
    assert urgency_boost(None) == 0.0
    assert urgency_boost(0) == 0.0
    assert urgency_boost(70) == 0.0
    assert apply_urgency(55.0, 40) == 55.0


def test_boost_rises_with_stress_and_saturates():
    low = urgency_boost(80)
    high = urgency_boost(163.76)  # Punjab, the worst state in the country -- just shy of
    # STRESS_SATURATION_PCT (165), so this is close to but not at the ceiling.
    extreme = urgency_boost(500)  # anything past saturation must clamp to the ceiling
    assert 0 < low < high < extreme
    assert extreme == pytest.approx(0.30)
    assert high <= 0.30


def test_apply_urgency_never_exceeds_100_and_never_creates_a_tie_at_the_top():
    """The old multiplier design clamped many high scores to exactly 100, which made the
    national ranking stop discriminating right where it matters. This must not happen."""
    a = apply_urgency(90.0, 163.76)
    b = apply_urgency(95.0, 163.76)
    assert a < 100.0
    assert b < 100.0
    assert a < b  # strictly increasing in the leak score


def test_apply_urgency_is_monotonic_in_stage():
    scores = [apply_urgency(70.0, stage) for stage in (None, 50, 75, 95, 148.77, 163.76)]
    assert scores == sorted(scores)


def test_apply_urgency_clamps_leak_score_input():
    """A pathological leak_score outside 0-100 must not blow up the result."""
    assert 0.0 <= apply_urgency(-10.0, 163.76) <= 100.0
    assert 0.0 <= apply_urgency(200.0, 163.76) <= 100.0


def test_categorise_matches_gec_2015_thresholds():
    assert categorise(50) == "Safe"
    assert categorise(70) == "Safe"
    assert categorise(70.01) == "Semi-Critical"
    assert categorise(90.01) == "Critical"
    assert categorise(100.01) == "Over-Exploited"


def test_effective_multiplier_reflects_the_actual_lift():
    boosted = apply_urgency(60.0, 163.76)
    assert effective_multiplier(60.0, 163.76) == pytest.approx(boosted / 60.0, abs=0.001)
    assert effective_multiplier(0.0, 163.76) == 1.0
