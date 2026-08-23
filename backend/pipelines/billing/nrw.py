"""Non-revenue water -> 0-100 billing score.

Owner: R2 (Data Engineer). Pure functions, no I/O.
"""

# Published Indian benchmarks put national NRW around 30-40%. We treat the middle of that
# band as "normal", and saturate the score well above it.
NRW_NORMAL_PCT = 32.0
NRW_SATURATION_PCT = 60.0


def nrw_pct(supplied_kl: float, billed_kl: float) -> float:
    if supplied_kl <= 0:
        return 0.0
    return round((supplied_kl - billed_kl) / supplied_kl * 100, 2)


def to_score(nrw: float, city_baseline: float = NRW_NORMAL_PCT) -> float:
    """Score how far above the city's normal loss rate this zone sits.

    Scoring against the city's own baseline rather than an absolute number means a city
    that is uniformly leaky doesn't light up entirely red -- we still surface its *worst*
    zones, which is what a repair crew actually needs.
    """
    if nrw <= city_baseline:
        return 0.0
    scaled = (nrw - city_baseline) / (NRW_SATURATION_PCT - city_baseline)
    return round(max(0.0, min(1.0, scaled)) * 100, 2)


def score_batch(rows: list[dict]) -> list[dict]:
    """rows: dicts with supplied_kl + billed_kl. Adds nrw_pct and score in place."""
    for row in rows:
        row["nrw_pct"] = nrw_pct(row["supplied_kl"], row["billed_kl"])

    if rows:
        values = sorted(r["nrw_pct"] for r in rows)
        baseline = values[len(values) // 2]  # city median loss rate
    else:
        baseline = NRW_NORMAL_PCT

    for row in rows:
        row["score"] = to_score(row["nrw_pct"], baseline)
    return rows
