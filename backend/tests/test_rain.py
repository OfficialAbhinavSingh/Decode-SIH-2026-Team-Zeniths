"""Tests for the rain de-confounder that protects the satellite signal from a monsoon.
See app/services/rain.py for the mechanism.
"""

from app.services.rain import (
    RAIN_SATURATION_MM_7D,
    RAIN_SUSPECT_MM_7D,
    SATELLITE_WEIGHT_FLOOR,
    is_flagged,
    rain_phrase,
    satellite_confidence,
)


def test_dry_week_keeps_full_confidence():
    assert satellite_confidence(None) == 1.0
    assert satellite_confidence(0) == 1.0
    assert satellite_confidence(RAIN_SUSPECT_MM_7D) == 1.0


def test_confidence_ramps_down_between_thresholds_and_never_hits_zero():
    mid = satellite_confidence((RAIN_SUSPECT_MM_7D + RAIN_SATURATION_MM_7D) / 2)
    assert SATELLITE_WEIGHT_FLOOR < mid < 1.0
    saturated = satellite_confidence(RAIN_SATURATION_MM_7D * 3)
    assert saturated == SATELLITE_WEIGHT_FLOOR


def test_is_flagged_matches_the_confidence_ramp_start():
    assert not is_flagged(RAIN_SUSPECT_MM_7D)
    assert is_flagged(RAIN_SUSPECT_MM_7D + 0.1)
    assert not is_flagged(None)


def test_rain_phrase_only_appears_when_flagged():
    assert rain_phrase(5.0) is None
    assert rain_phrase(None) is None
    phrase = rain_phrase(80.0)
    assert phrase is not None and "80" in phrase
