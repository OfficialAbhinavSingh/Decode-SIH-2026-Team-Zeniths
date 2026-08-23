"""NDVI anomaly -> 0-100 satellite score.

Owner: R1 (Satellite & Geo).

The scoring functions are pure so you can tune them without touching the network.
"""

from statistics import median

# An NDVI anomaly of this much above baseline is treated as a maximally suspicious zone.
# Tune against a zone you know is leaking, or against the spread of your own export.
ANOMALY_SATURATION = 0.20

# Below this, the difference is noise, not signal.
ANOMALY_FLOOR = 0.02


def raw_anomaly(ndvi_mean: float, ndvi_baseline: float) -> float:
    return ndvi_mean - ndvi_baseline


def city_relative_anomaly(anomalies: list[float]) -> list[float]:
    """Subtract the city-wide median anomaly from each zone.

    This is the cheap defence against rain (risk R1): if it rained two days ago the whole
    city greens up together, the median rises with it, and the differences that survive are
    the zones that are wet for a reason other than weather.
    """
    if not anomalies:
        return []
    city_median = median(anomalies)
    return [a - city_median for a in anomalies]


def to_score(relative_anomaly: float) -> float:
    """Map a city-relative NDVI anomaly onto 0-100."""
    if relative_anomaly <= ANOMALY_FLOOR:
        return 0.0
    scaled = (relative_anomaly - ANOMALY_FLOOR) / (ANOMALY_SATURATION - ANOMALY_FLOOR)
    return round(max(0.0, min(1.0, scaled)) * 100, 2)


def score_batch(rows: list[dict]) -> list[dict]:
    """rows: dicts with ndvi_mean + ndvi_baseline. Adds ndvi_anomaly and score in place."""
    anomalies = [raw_anomaly(r["ndvi_mean"], r["ndvi_baseline"]) for r in rows]
    relative = city_relative_anomaly(anomalies)
    for row, absolute, rel in zip(rows, anomalies, relative, strict=True):
        row["ndvi_anomaly"] = round(absolute, 4)
        row["score"] = to_score(rel)
    return rows
