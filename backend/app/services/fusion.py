"""Fusion engine -- the core of NeerDrishti AI.

Owner: R3 (Backend & Fusion).

Turns up to three independent 0-100 signals into one priority score per zone, plus a
confidence level and a human-readable reason. The rule is documented in
docs/DATA-CONTRACT.md so the whole team can defend it on stage.

The scoring functions here are pure -- no DB, no I/O -- so they are cheap to test.
`run_fusion()` is the only part that touches the database.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BillingSignal, CitizenReport, SatelliteSignal, Zone, ZoneScore, utcnow

# Satellite is weighted highest: it is the signal nobody else in this problem statement has.
WEIGHTS = {"satellite": 0.40, "billing": 0.35, "citizen": 0.25}

# A citizen report window this long, and the count that saturates the citizen score.
CITIZEN_WINDOW_DAYS = 30
CITIZEN_SATURATION = 5

# Sub-scores this far apart mean the signals disagree, so confidence drops.
AGREEMENT_SPREAD = 25.0


def fuse(
    satellite: float | None,
    billing: float | None,
    citizen: float | None,
) -> tuple[float, str, int]:
    """Combine present signals into (fusion_score, confidence, signals_used).

    A missing signal is *absent*, not zero: the weights of the signals that are present
    are renormalised. A zone with only a strong satellite signal scores high, instead of
    being punished down to 40% for data the municipality never collected.
    """
    present = {
        "satellite": satellite,
        "billing": billing,
        "citizen": citizen,
    }
    present = {k: v for k, v in present.items() if v is not None}

    if not present:
        return 0.0, "low", 0

    weight_sum = sum(WEIGHTS[k] for k in present)
    score = sum(WEIGHTS[k] * v for k, v in present.items()) / weight_sum

    values = list(present.values())
    spread = max(values) - min(values)
    if len(present) == 3 and spread <= AGREEMENT_SPREAD:
        confidence = "high"
    elif len(present) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return round(score, 2), confidence, len(present)


def citizen_score(report_count: int) -> float:
    """Report count -> 0-100. Saturates, so one loud street can't dominate the map."""
    if report_count <= 0:
        return 0.0
    return round(min(1.0, report_count / CITIZEN_SATURATION) * 100, 2)


def explain(
    zone_name: str,
    satellite: float | None,
    billing: float | None,
    citizen: float | None,
    nrw_pct: float | None,
    ndvi_anomaly: float | None,
    report_count: int,
    confidence: str,
    signals_used: int,
) -> str:
    """The sentence the dashboard shows. This is the most important pixel in the demo."""
    parts: list[str] = []
    if satellite is not None and ndvi_anomaly is not None:
        parts.append(f"NDVI {ndvi_anomaly:+.2f} vs baseline")
    if billing is not None and nrw_pct is not None:
        parts.append(f"{nrw_pct:.0f}% non-revenue water")
    if report_count:
        plural = "s" if report_count != 1 else ""
        parts.append(f"{report_count} citizen report{plural} in {CITIZEN_WINDOW_DAYS} days")

    if not parts:
        return f"{zone_name}: no signals available yet."

    if confidence == "high":
        tail = " -- all three signals agree."
    elif signals_used == 3:
        # Three signals present but far apart: still worth a crew, worth saying why.
        tail = " -- all three signals present but they disagree, verify before digging."
    elif signals_used == 2:
        tail = " -- two of three signals available."
    else:
        tail = " -- single signal only, treat as a lead, not a finding."
    return ", ".join(parts) + tail


def percentile_rank(values: list[float]) -> list[float]:
    """Spread scores across 0-100 by within-city percentile.

    Without this every zone lands in the 55-65 band and the map is one flat colour --
    technically correct, visually useless. Ordering is unchanged.
    """
    if not values:
        return []
    if len(values) == 1:
        return [values[0]]

    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    last = len(values) - 1
    for position, original_index in enumerate(order):
        out[original_index] = round(position / last * 100, 2)
    return out


def _latest(rows: list) -> object | None:
    return rows[0] if rows else None


# seed.py writes source="seed"; R1's real pipeline writes source="sentinel2-gee". A real
# reading must always beat a seeded one even when the seeded row carries a later
# observed_on -- otherwise `python seed.py` (which the offline-demo fallback and every
# teammate's local setup run) silently masks real satellite data that ingested fine.
# False sorts before True in SQL, so non-seed rows come first.
_REAL_SATELLITE_FIRST = (SatelliteSignal.source == "seed").asc()


def run_fusion(db: Session, city: str) -> int:
    """Recompute zone_scores for every zone in `city`. Returns the number scored."""
    zones = db.scalars(select(Zone).where(Zone.city == city)).all()
    if not zones:
        return 0

    since = datetime.now(timezone.utc) - timedelta(days=CITIZEN_WINDOW_DAYS)
    computed_at = utcnow()
    rows: list[dict] = []

    for zone in zones:
        sat = _latest(
            db.scalars(
                select(SatelliteSignal)
                .where(SatelliteSignal.zone_id == zone.id)
                .order_by(_REAL_SATELLITE_FIRST, SatelliteSignal.observed_on.desc())
                .limit(1)
            ).all()
        )
        bill = _latest(
            db.scalars(
                select(BillingSignal)
                .where(BillingSignal.zone_id == zone.id)
                .order_by(BillingSignal.period_end.desc())
                .limit(1)
            ).all()
        )
        reports = db.scalars(
            select(CitizenReport).where(
                CitizenReport.zone_id == zone.id,
                CitizenReport.reported_at >= since,
                CitizenReport.status != "dismissed",
            )
        ).all()

        report_count = len(reports)
        cit = citizen_score(report_count) if report_count else None
        sat_score = sat.score if sat else None
        bill_score = bill.score if bill else None

        score, confidence, used = fuse(sat_score, bill_score, cit)
        rows.append(
            {
                "zone": zone,
                "satellite_score": sat_score,
                "billing_score": bill_score,
                "citizen_score": cit,
                "raw": score,
                "confidence": confidence,
                "signals_used": used,
                "explanation": explain(
                    zone.name,
                    sat_score,
                    bill_score,
                    cit,
                    bill.nrw_pct if bill else None,
                    sat.ndvi_anomaly if sat else None,
                    report_count,
                    confidence,
                    used,
                ),
            }
        )

    spread = percentile_rank([r["raw"] for r in rows])
    for row, value in zip(rows, spread, strict=True):
        row["fusion_score"] = value

    rows.sort(key=lambda r: r["fusion_score"], reverse=True)

    # One score row per zone per run: clear the city's old rows, then insert fresh.
    old = db.scalars(
        select(ZoneScore).join(Zone, ZoneScore.zone_id == Zone.id).where(Zone.city == city)
    ).all()
    for row in old:
        db.delete(row)

    for rank, row in enumerate(rows, start=1):
        db.add(
            ZoneScore(
                zone_id=row["zone"].id,
                computed_at=computed_at,
                satellite_score=row["satellite_score"],
                billing_score=row["billing_score"],
                citizen_score=row["citizen_score"],
                fusion_score=row["fusion_score"],
                confidence=row["confidence"],
                signals_used=row["signals_used"],
                rank=rank,
                explanation=row["explanation"],
            )
        )

    db.commit()
    return len(rows)
