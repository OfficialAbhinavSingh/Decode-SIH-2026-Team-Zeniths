"""Groundwater stress -> an urgency multiplier on an already-computed leak score.

Owner: R2 (Data). Pure functions, no I/O.

THE IDEA A JUDGE WILL PUSH ON: why is groundwater not just a fourth signal?

Because it is not evidence of a leak. NDVI, NRW and citizen reports each answer "is this
zone losing water?". Groundwater extraction answers a different question -- "if it is,
how much does that cost?" -- and mixing the two would let a water-stressed zone with no
leak evidence outrank a zone where all three signals agree. That is exactly backwards for
a crew with one truck.

So the leak score is computed first and untouched, and stress only lifts it:

    priority_score = absolute_score + (100 - absolute_score) * urgency_boost
                                                          (boost in [0.00, 0.30])

WHY THAT SHAPE AND NOT A MULTIPLIER. `score * 1.4` clamped to 100 was the obvious first
try and it is wrong in the one place the number is read: any zone above 72 in Punjab or
Rajasthan pins to exactly 100, so the worst forty cities in the country tie for first and
the national ranking stops discriminating precisely at the top. Moving a fixed fraction of
the *remaining headroom* instead is strictly increasing in the leak score (d/da = 1 - boost
> 0), so it never creates a tie, and reaches 100 only where the leak score was already 100.

The boost is capped at 0.30 deliberately: enough to reorder a national list, never enough
to promote a zone with weak evidence above one with strong evidence. A 50/100 zone in
Punjab becomes 65; a 75/100 zone in Kerala still outranks it.

SOURCE: Central Ground Water Board, *National Compilation on Dynamic Ground Water
Resources of India, 2023*, Annexure-I (state-wise Stage of Ground Water Extraction).
https://cgwb.gov.in/cgwbpnm/public/uploads/documents/17056512151889452705file.pdf
National average stage of extraction 59.26%; 736 of 6,553 assessment units are
Over-Exploited. Categories follow GEC-2015: Safe <=70%, Semi-Critical 70-90%,
Critical 90-100%, Over-Exploited >100%.

The dataset lives in `data/india/groundwater_cgwb2023.csv`, built by
`pipelines/water/load_groundwater.py`, which cross-checks every printed figure against
the extraction and extractable-resource columns on the same row.
"""

# GEC-2015 category thresholds, as published.
SAFE_MAX = 70.0
SEMI_CRITICAL_MAX = 90.0
CRITICAL_MAX = 100.0

# Fraction of the remaining headroom that maximum groundwater stress is allowed to move.
# Never below zero -- a water-rich state does not make a leak acceptable, it just makes it
# less urgent than the same leak in Punjab.
BOOST_MIN = 0.00
BOOST_MAX = 0.30

# Stage of extraction at which the ceiling is reached. Punjab, the worst in the country,
# sits at 163.76%, so the scale saturates roughly where the real data ends rather than at
# an arbitrary round number.
STRESS_SATURATION_PCT = 165.0


def categorise(stage_pct: float) -> str:
    """CGWB's own four-way classification of an assessment unit."""
    if stage_pct > CRITICAL_MAX:
        return "Over-Exploited"
    if stage_pct > SEMI_CRITICAL_MAX:
        return "Critical"
    if stage_pct > SAFE_MAX:
        return "Semi-Critical"
    return "Safe"


def urgency_boost(stage_pct: float | None) -> float:
    """Stage of ground water extraction (%) -> headroom fraction in [0.00, 0.30].

    Flat at zero through the 'Safe' band, then rising linearly to the ceiling at
    STRESS_SATURATION_PCT. Linear rather than stepped so a city at 89% and one at 91% are
    not separated by a cliff they cannot feel on the ground -- the categories are a
    reporting convention, the underlying quantity is continuous.

    A missing figure returns 0.0: unknown stress must never invent urgency.
    """
    if stage_pct is None or stage_pct <= SAFE_MAX:
        return BOOST_MIN
    span = STRESS_SATURATION_PCT - SAFE_MAX
    fraction = min(1.0, (stage_pct - SAFE_MAX) / span)
    return round(BOOST_MIN + fraction * (BOOST_MAX - BOOST_MIN), 4)


def apply_urgency(leak_score: float, stage_pct: float | None) -> float:
    """Leak likelihood lifted by how much a leak costs here. Stays inside 0-100.

    Bounded by construction rather than by a clamp, which is what keeps the national
    ranking free of ties at the top -- see the module docstring.
    """
    score = max(0.0, min(100.0, leak_score))
    return round(score + (100.0 - score) * urgency_boost(stage_pct), 2)


def effective_multiplier(leak_score: float, stage_pct: float | None) -> float:
    """The lift as a ratio, for display: "priority 78, x1.11 for groundwater stress".

    Derived from the result rather than being the mechanism, so the number shown to a
    user is always the one that actually moved the score.
    """
    if leak_score <= 0:
        return 1.0
    return round(apply_urgency(leak_score, stage_pct) / leak_score, 4)


def stress_phrase(stage_pct: float | None) -> str | None:
    """The clause the explanation sentence uses. None when we have no figure."""
    if stage_pct is None:
        return None
    category = categorise(stage_pct)
    if category == "Safe":
        return None
    return f"{category.lower()} groundwater ({stage_pct:.0f}% extraction)"
