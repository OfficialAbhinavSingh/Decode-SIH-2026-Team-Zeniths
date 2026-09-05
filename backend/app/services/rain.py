"""Rain -> how far to trust today's satellite reading.

Owner: R2 (Data). Pure functions, no I/O. The fetcher that produces the underlying
rainfall rows lives in `pipelines/water/rainfall.py`; this module is the scoring half,
kept in `app/services/` because fusion depends on it and nothing in `app/` should import
from `pipelines/`.

THE RISK THIS CLOSES: the satellite lane calls a zone suspicious when its NDVI runs above
its own 3-year baseline, on the theory that soil over a leaking main stays wetter and
greener. Rain does exactly the same thing to exactly the same pixels. Run this through an
Indian monsoon without a rainfall check and every zone in the city lights up on the same
day -- which is not a leak map, it is a weather map with extra steps.

`ndvi.city_relative_anomaly()` already subtracts the city-wide median anomaly, which
removes rain that fell evenly, and costs nothing. What it cannot do is say *when the whole
reading is untrustworthy*: after 60 mm in a week the surviving between-zone differences
are drainage and soil type, not leaks, and the honest move is to lean on billing and
citizen reports instead -- and to say why on screen.
"""

# Rain in the last 7 days above this makes an NDVI anomaly unreadable as a leak signal.
# ~20 mm is roughly two ordinary rain days: enough to green a city, well below a monsoon
# week. Below it we trust the satellite lane at full weight.
RAIN_SUSPECT_MM_7D = 20.0

# Above this the reading carries essentially no leak information -- a heavy monsoon week.
RAIN_SATURATION_MM_7D = 120.0

# The floor the satellite weight is allowed to fall to. Never zero: a zone that is wetter
# than its neighbours in the same storm is still telling us something, just faintly.
SATELLITE_WEIGHT_FLOOR = 0.25


def satellite_confidence(rain_mm_7d: float | None) -> float:
    """Recent rain -> a multiplier in [0.25, 1.0] on the satellite signal's weight.

    Ramps down linearly between the suspect and saturation thresholds rather than
    switching off at a line, because there is nothing physical about 20 mm -- it is where
    confidence starts to go, not where it ends.
    """
    if rain_mm_7d is None or rain_mm_7d <= RAIN_SUSPECT_MM_7D:
        return 1.0
    span = RAIN_SATURATION_MM_7D - RAIN_SUSPECT_MM_7D
    fraction = min(1.0, (rain_mm_7d - RAIN_SUSPECT_MM_7D) / span)
    return round(1.0 - fraction * (1.0 - SATELLITE_WEIGHT_FLOOR), 4)


def is_flagged(rain_mm_7d: float | None) -> bool:
    """Whether the UI should say out loud that rain is affecting this reading."""
    return rain_mm_7d is not None and rain_mm_7d > RAIN_SUSPECT_MM_7D


def rain_phrase(rain_mm_7d: float | None) -> str | None:
    """The clause the explanation sentence uses. None when rain is not a factor."""
    if not is_flagged(rain_mm_7d):
        return None
    return f"{rain_mm_7d:.0f} mm of rain in 7 days, so the satellite reading is down-weighted"
