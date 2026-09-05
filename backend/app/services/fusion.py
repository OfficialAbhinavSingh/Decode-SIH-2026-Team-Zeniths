"""Fusion engine -- the core of NeerDrishti AI.

Owner: R3 (Backend & Fusion).

Turns up to three independent 0-100 signals into one priority score per zone, plus a
confidence level and a human-readable reason. The rule is documented in
docs/DATA-CONTRACT.md so the whole team can defend it on stage.

The scoring functions here are pure -- no DB, no I/O -- so they are cheap to test.
`run_fusion()` and `run_national_fusion()` are the only parts that touch the database.

WHAT PAN-INDIA COVERAGE CHANGED (and what it deliberately did not)

The three-signal weighted average is untouched: same weights, same renormalisation on a
missing signal, same confidence rule. Everything below wraps it rather than replacing it.

  1. Rain adjustment. Heavy recent rain greens a whole city, so the satellite lane's
     weight is scaled by `rainfall.satellite_confidence()` -- down to a floor of 0.25,
     never to zero -- and the explanation says so out loud. This is the honest answer to
     "how do you know that is a leak and not last Tuesday's storm?".

  2. Two scores, not one. `fusion_score` stays a within-city percentile, because that is
     what stops a city map from being one flat colour. But a percentile means every city
     on earth has a zone at 100, so it cannot rank zones *between* cities.
     `absolute_score` is the raw weighted average and is comparable nationally.

  3. Urgency, applied last. `priority_score = absolute_score x urgency_multiplier`, where
     the multiplier comes from CGWB groundwater stress and is capped at 1.4. Groundwater
     is not evidence of a leak, so it never enters the average -- it only reorders zones
     that already have evidence. See services/urgency.py for the argument.

  4. An impact figure per zone, so the output is kilolitres and rupees rather than a
     number out of a hundred. See services/impact.py.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    BillingSignal,
    CitizenReport,
    City,
    CityScore,
    GroundwaterStress,
    RainfallObservation,
    SatelliteSignal,
    Zone,
    ZoneScore,
    utcnow,
)
from . import impact
from .rain import is_flagged, rain_phrase, satellite_confidence
from .urgency import apply_urgency, categorise, effective_multiplier, stress_phrase

# seed.py and pipelines/geo/seed_national.py write source="seed"; a real pipeline writes
# source="sentinel2-gee". A real reading must always beat a seeded one even when the
# seeded row carries a later observed_on -- otherwise reseeding a demo city (which the
# offline-demo fallback and every teammate's local setup do) silently masks real
# satellite data that already ingested fine. Expressed as the sort key `_Context` passes
# to `_latest_signal_map`: `source != "seed"` is truthier for a real row, so it wins the
# max() comparison regardless of date. (Landed on main as a per-zone SQL ORDER BY; this
# is the equivalent for the batched national query.)

# Satellite is weighted highest: it is the signal nobody else in this problem statement has.
WEIGHTS = {"satellite": 0.40, "billing": 0.35, "citizen": 0.25}

# A citizen report window this long, and the count that saturates the citizen score.
CITIZEN_WINDOW_DAYS = 30
CITIZEN_SATURATION = 5

# Report statuses that must not contribute to the citizen score.
#
# `duplicate` is set by the intake dedupe in routers/reports.py, which logs "Dropped
# duplicate report" as it does so -- the intent there is unmistakable. Counting those rows
# anyway defeated the 200m/6hr clustering completely: one person messaging the bot four
# times about the same puddle saturated the zone's citizen score exactly as four separate
# residents would. Production had 8 such rows, all on one zone, and they carried it to
# rank 6. (Landed on main in #13, merged in here for pan-India coverage.)
UNCOUNTED_REPORT_STATUSES = ("dismissed", "duplicate")

# Sub-scores this far apart mean the signals disagree, so confidence drops.
AGREEMENT_SPREAD = 25.0

# How much a zone's score is discounted for the signals it does *not* have.
#
# Renormalising alone is not enough. It divides by the weight of the signals present, so a
# zone with one billing reading of 86 scores 86 -- exactly what a zone with three sources
# agreeing at 86 scores. Percentile-ranking then pushes whichever is highest to 100, and a
# single unverified number can top the repair list. That is not a hypothetical: with the
# real Sentinel-2 export loaded, three of the top six zones were single-signal leads, and
# the only zone with all three signals sat at rank 5. (Landed on main in #11.)
#
# So coverage is a multiplier, not a veto. One signal is still a lead worth showing -- it
# just cannot outrank corroboration. A lone satellite score of 90 lands at 63, not at 36
# (which is what refusing to renormalise would give it) and not at 90.
COVERAGE_FACTOR = {0: 0.0, 1: 0.70, 2: 0.90, 3: 1.0}

# A zone at or above this priority is "high priority" in the city rollup.
HIGH_PRIORITY_THRESHOLD = 70.0


def fuse(
    satellite: float | None,
    billing: float | None,
    citizen: float | None,
    satellite_weight_factor: float = 1.0,
) -> tuple[float, str, int]:
    """Combine present signals into (fusion_score, confidence, signals_used).

    A missing signal is *absent*, not zero: the weights of the signals that are present
    are renormalised. A zone with only a strong satellite signal scores high, instead of
    being punished down to 40% for data the municipality never collected.

    `satellite_weight_factor` scales the satellite weight only, for the rain adjustment.
    It defaults to 1.0, so every existing caller and the frozen contract are unaffected.
    A factor below 1 shifts influence onto billing and citizen reports without dropping
    the satellite reading, because a zone wetter than its neighbours *in the same storm*
    is still saying something -- just more quietly.

    The result is then scaled by COVERAGE_FACTOR, so a zone resting on one signal cannot
    outrank one where three independent sources corroborate.
    """
    present = {
        "satellite": satellite,
        "billing": billing,
        "citizen": citizen,
    }
    present = {k: v for k, v in present.items() if v is not None}

    if not present:
        return 0.0, "low", 0

    weights = dict(WEIGHTS)
    weights["satellite"] *= max(0.0, satellite_weight_factor)

    weight_sum = sum(weights[k] for k in present)
    if weight_sum <= 0:
        return 0.0, "low", 0
    score = sum(weights[k] * v for k, v in present.items()) / weight_sum
    score *= COVERAGE_FACTOR[len(present)]

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
    stress: str | None = None,
    rain_mm_7d: float | None = None,
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

    sentence = ", ".join(parts) + tail

    # Context clauses come after the verdict, never inside it. Neither groundwater stress
    # nor rainfall is evidence that this zone is leaking -- one says what a leak here
    # costs, the other says how much of the above to believe -- and the sentence must not
    # read as though they were part of the finding.
    context = [clause for clause in (rain_phrase(rain_mm_7d), stress) if clause]
    if context:
        sentence += " " + "; ".join(c[0].upper() + c[1:] for c in context) + "."
    return sentence


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


# ---------------------------------------------------------------------------
# Database side. Everything above is pure; everything below reads and writes.
# ---------------------------------------------------------------------------


def _latest_signal_map(db: Session, model, key) -> dict[str, object]:
    """zone_id -> that zone's best row of `model`, by `key(row)`, highest wins.

    One query for the whole country rather than one per zone. At 7,000 zones the
    per-zone version is 7,000 round trips, which is roughly a minute of latency on a
    managed database and the reason the national fusion run used to time out.

    Reduced in Python rather than SQL (a group-by/max, or Postgres's DISTINCT ON) because
    `key` needs to express "a real reading beats a seeded one regardless of date" for
    satellite signals -- an aggregate a portable group-by can't express -- not just
    "latest date". Row counts per zone stay small (one ingest per period), so fetching
    every row for the whole country and reducing in memory is still one round trip and
    comfortably fast; see `_Context` for the two `key` functions actually used.
    """
    rows = db.scalars(select(model)).all()
    best: dict[str, object] = {}
    for row in rows:
        if row.zone_id not in best or key(row) > key(best[row.zone_id]):
            best[row.zone_id] = row
    return best


def _report_counts(db: Session, since: datetime) -> dict[str, int]:
    """zone_id -> live citizen reports in the rolling window."""
    rows = db.execute(
        select(CitizenReport.zone_id, func.count(CitizenReport.id))
        .where(
            CitizenReport.zone_id.is_not(None),
            CitizenReport.reported_at >= since,
            CitizenReport.status.notin_(UNCOUNTED_REPORT_STATUSES),
        )
        .group_by(CitizenReport.zone_id)
    ).all()
    return {zone_id: count for zone_id, count in rows}


def _stress_map(db: Session) -> dict[str, GroundwaterStress]:
    """Lower-cased state name -> its groundwater row.

    Case-folded because the two datasets disagree on it: GeoNames writes
    "Jammu and Kashmir", CGWB's annexure writes "Jammu And Kashmir". Joining on the raw
    string silently drops those states to no-stress, which is invisible in the UI and
    wrong in exactly the places that matter.
    """
    out: dict[str, GroundwaterStress] = {}
    for row in db.scalars(select(GroundwaterStress).where(GroundwaterStress.district.is_(None))):
        out[row.state.strip().casefold()] = row
    return out


def _rain_map(db: Session) -> dict[str, RainfallObservation]:
    """city_code -> its most recent rainfall observation."""
    newest = (
        select(
            RainfallObservation.city_code.label("city_code"),
            func.max(RainfallObservation.observed_on).label("latest"),
        )
        .group_by(RainfallObservation.city_code)
        .subquery()
    )
    rows = db.scalars(
        select(RainfallObservation).join(
            newest,
            (RainfallObservation.city_code == newest.c.city_code)
            & (RainfallObservation.observed_on == newest.c.latest),
        )
    ).all()
    return {row.city_code: row for row in rows}


class _Context:
    """Everything fusion needs, fetched once for the whole run."""

    def __init__(self, db: Session):
        # Real beats seed regardless of date -- see `_REAL_SATELLITE_FIRST`'s docstring.
        self.satellite = _latest_signal_map(
            db, SatelliteSignal, lambda r: (r.source != "seed", r.observed_on, r.id)
        )
        self.billing = _latest_signal_map(
            db, BillingSignal, lambda r: (r.period_end, r.id)
        )
        self.reports = _report_counts(
            db, datetime.now(timezone.utc) - timedelta(days=CITIZEN_WINDOW_DAYS)
        )
        self.stress = _stress_map(db)
        self.rain = _rain_map(db)

    def stress_for(self, zone: Zone) -> GroundwaterStress | None:
        if not zone.state:
            return None
        return self.stress.get(zone.state.strip().casefold())

    def rain_for(self, zone: Zone) -> RainfallObservation | None:
        if not zone.city_code:
            return None
        return self.rain.get(zone.city_code)


def _score_zones(zones: list[Zone], ctx: _Context, computed_at: datetime) -> list[dict]:
    """Score one city's zones. Pure with respect to the DB -- reads only from `ctx`."""
    rows: list[dict] = []

    for zone in zones:
        sat = ctx.satellite.get(zone.id)
        bill = ctx.billing.get(zone.id)
        report_count = ctx.reports.get(zone.id, 0)

        rain = ctx.rain_for(zone)
        rain_mm_7d = rain.rain_mm_7d if rain else None
        weight_factor = satellite_confidence(rain_mm_7d)

        cit = citizen_score(report_count) if report_count else None
        sat_score = sat.score if sat else None
        bill_score = bill.score if bill else None

        score, confidence, used = fuse(sat_score, bill_score, cit, weight_factor)

        stress = ctx.stress_for(zone)
        stage = stress.stage_of_extraction_pct if stress else None

        period_days = None
        if bill and bill.period_start and bill.period_end:
            period_days = (bill.period_end - bill.period_start).days + 1
        ledger = impact.ledger(
            zone.population,
            bill.nrw_pct if bill else None,
            bill.supplied_kl if bill else None,
            period_days,
        )

        rows.append(
            {
                "zone": zone,
                "satellite_score": sat_score,
                "billing_score": bill_score,
                "citizen_score": cit,
                "raw": score,
                "confidence": confidence,
                "signals_used": used,
                "priority_score": apply_urgency(score, stage),
                "urgency_multiplier": effective_multiplier(score, stage),
                "groundwater_stress_pct": stage,
                "groundwater_category": categorise(stage) if stage is not None else None,
                "rain_flagged": is_flagged(rain_mm_7d),
                "rain_mm_7d": rain_mm_7d,
                "water_at_risk_kld": ledger["water_at_risk_kld"],
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
                    stress_phrase(stage),
                    rain_mm_7d,
                ),
            }
        )

    # Percentile within this city only -- see the module docstring on why there are two
    # scores. `absolute_score` keeps the comparable number that ranking nationally needs.
    spread = percentile_rank([r["raw"] for r in rows])
    for row, value in zip(rows, spread, strict=True):
        row["absolute_score"] = row["raw"]
        row["fusion_score"] = value

    rows.sort(key=lambda r: r["fusion_score"], reverse=True)
    return rows


def _to_model(row: dict, rank: int, computed_at: datetime) -> ZoneScore:
    return ZoneScore(
        zone_id=row["zone"].id,
        computed_at=computed_at,
        satellite_score=row["satellite_score"],
        billing_score=row["billing_score"],
        citizen_score=row["citizen_score"],
        fusion_score=row["fusion_score"],
        absolute_score=row["absolute_score"],
        priority_score=row["priority_score"],
        urgency_multiplier=row["urgency_multiplier"],
        groundwater_stress_pct=row["groundwater_stress_pct"],
        groundwater_category=row["groundwater_category"],
        rain_flagged=row["rain_flagged"],
        rain_mm_7d=row["rain_mm_7d"],
        water_at_risk_kld=row["water_at_risk_kld"],
        confidence=row["confidence"],
        signals_used=row["signals_used"],
        rank=rank,
        explanation=row["explanation"],
    )


def _city_rollup(city: City | None, zones_rows: list[dict], computed_at: datetime) -> dict | None:
    """Collapse a city's scored zones into the one row the national map draws."""
    if not zones_rows or city is None:
        return None
    priorities = [r["priority_score"] for r in zones_rows]
    top = max(zones_rows, key=lambda r: r["priority_score"])
    return {
        "city_code": city.code,
        "city": city.name,
        "state": city.state,
        "computed_at": computed_at,
        "zones_scored": len(zones_rows),
        "mean_priority": round(sum(priorities) / len(priorities), 2),
        "max_priority": round(max(priorities), 2),
        "hotspot_zone_id": top["zone"].id,
        "high_priority_zones": sum(1 for p in priorities if p >= HIGH_PRIORITY_THRESHOLD),
        "groundwater_stress_pct": top["groundwater_stress_pct"],
        "water_at_risk_kld": round(sum(r["water_at_risk_kld"] or 0 for r in zones_rows), 2),
        "population_served": sum(r["zone"].population or 0 for r in zones_rows),
    }


def run_fusion(db: Session, city: str) -> int:
    """Recompute zone_scores for every zone in `city`. Returns the number scored.

    Unchanged in contract from the single-city MVP: same name, same arguments, same
    return. What it writes is richer, and every added column is nullable.
    """
    zones = db.scalars(select(Zone).where(Zone.city == city)).all()
    if not zones:
        return 0

    ctx = _Context(db)
    computed_at = utcnow()
    rows = _score_zones(list(zones), ctx, computed_at)

    # One score row per zone per run: clear the city's old rows, then insert fresh.
    old = db.scalars(
        select(ZoneScore).join(Zone, ZoneScore.zone_id == Zone.id).where(Zone.city == city)
    ).all()
    for row in old:
        db.delete(row)

    for rank, row in enumerate(rows, start=1):
        db.add(_to_model(row, rank, computed_at))

    city_row = db.scalars(select(City).where(City.name == city).limit(1)).first()
    if city_row is not None:
        db.execute(CityScore.__table__.delete().where(CityScore.city_code == city_row.code))
        rollup = _city_rollup(city_row, rows, computed_at)
        if rollup:
            db.add(CityScore(rank=1, **rollup))

    db.commit()
    return len(rows)


def run_national_fusion(db: Session, limit_cities: int | None = None) -> dict:
    """Score every zone in the country and rank the cities against each other.

    Returns a summary the API and the n8n cron both surface. This is one pass over the
    whole database, not 500 calls to `run_fusion` -- the signal lookups are shared, which
    is the difference between a national recompute taking seconds and taking minutes.
    """
    cities = db.scalars(select(City).order_by(City.population.desc())).all()
    if limit_cities:
        cities = list(cities)[:limit_cities]
    by_code = {c.code: c for c in cities}
    wanted = set(by_code)

    zones = db.scalars(select(Zone)).all()
    grouped: dict[str, list[Zone]] = defaultdict(list)
    orphans: list[Zone] = []
    for zone in zones:
        if zone.city_code and zone.city_code in wanted:
            grouped[zone.city_code].append(zone)
        elif not zone.city_code:
            # A zone loaded from a pre-national geojson has no city_code. It still gets
            # scored, grouped by its city name, just without a national rollup row.
            orphans.append(zone)

    ctx = _Context(db)
    computed_at = utcnow()

    db.execute(ZoneScore.__table__.delete())
    db.execute(CityScore.__table__.delete())

    rollups: list[dict] = []
    zones_scored = 0

    for code, city_zones in grouped.items():
        rows = _score_zones(city_zones, ctx, computed_at)
        for rank, row in enumerate(rows, start=1):
            db.add(_to_model(row, rank, computed_at))
        zones_scored += len(rows)
        rollup = _city_rollup(by_code[code], rows, computed_at)
        if rollup:
            rollups.append(rollup)

    if orphans:
        by_name: dict[str, list[Zone]] = defaultdict(list)
        for zone in orphans:
            by_name[zone.city].append(zone)
        for city_zones in by_name.values():
            rows = _score_zones(city_zones, ctx, computed_at)
            for rank, row in enumerate(rows, start=1):
                db.add(_to_model(row, rank, computed_at))
            zones_scored += len(rows)

    # National ranking is by the city's worst zone, not its average: a utility is called
    # out for the street it has not fixed, and averaging 120 zones buries exactly the one
    # a crew should be sent to.
    rollups.sort(key=lambda r: r["max_priority"], reverse=True)
    for rank, rollup in enumerate(rollups, start=1):
        db.add(CityScore(rank=rank, **rollup))

    db.commit()
    return {
        "zones_scored": zones_scored,
        "cities_scored": len(rollups),
        "unassigned_zones": len(orphans),
        "water_at_risk_kld": round(sum(r["water_at_risk_kld"] for r in rollups), 2),
        "population_covered": sum(r["population_served"] for r in rollups),
        "computed_at": computed_at.isoformat(),
    }
