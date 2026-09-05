"""Every scored zone in the country, in one FeatureCollection. Owner: R3 (Backend & Fusion).

`/api/scores` and `/api/scores/geojson` answer "which zone in *this city* should a crew
open first". They cannot answer "which zone in India", and not for want of a WHERE clause:
`zone_scores.fusion_score` is a **within-city percentile** -- fusion.py runs
`percentile_rank()` over one city's zones -- so every city's worst zone reads exactly
100.0. Dropping the city filter would return 234 zones tied at 100.0, ranked by nothing.

What survives the percentile is the raw material. `satellite_score`, `billing_score` and
`citizen_score` are stored **absolute**, so the published rule can simply be re-run over a
different population: `fuse()` for the magnitude, `percentile_rank()` for the spread, the
whole country instead of one city. Same weights, same coverage discount, same code --
imported from services/fusion.py rather than restated, so the national view cannot drift
from the city view.

Nothing here writes. No column, no table, no migration: it is a read of rows that already
exist, re-ranked at request time.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Zone, ZoneScore
from ..services.fusion import fuse, percentile_rank

router = APIRouter(prefix="/api/national", tags=["national"])

# ~1.1 m at the equator. The stored polygons carry six, and shipping the sixth costs about
# 60 KB across 6,000 zones to place a 1.3 km square a hundred millimetres more precisely.
COORD_DECIMALS = 5

# A guard, not a page size. The response is one FeatureCollection by design -- the map
# needs every polygon at once or it is not a map of India -- so this exists only to fail
# loudly rather than stream half a gigabyte if someone points this at a database far larger
# than the synthetic registry.
MAX_ZONES = 20_000


def _round_coords(node):
    """Round every coordinate in a GeoJSON geometry, at whatever nesting depth."""
    if isinstance(node, (int, float)):
        return round(node, COORD_DECIMALS)
    if isinstance(node, list):
        return [_round_coords(child) for child in node]
    return node


def rank_zones(pairs) -> list[dict]:
    """(ZoneScore, Zone) pairs -> rows carrying a national percentile and a national rank.

    Pure: no session, no I/O, so the ranking rule is testable without a database. Takes the
    query result rather than running the query, for the same reason.
    """
    rows = []
    for score, zone in pairs:
        absolute, _confidence, _used = fuse(
            score.satellite_score, score.billing_score, score.citizen_score
        )
        rows.append(
            {
                "zone": zone,
                "score": score,
                # The magnitude the national percentile is computed from. Kept so the
                # ordering can be explained, and so a caller can tell a zone that is 90th
                # percentile at 71 points from one that is 90th percentile at 12.
                "absolute_score": absolute,
            }
        )

    # Establish the national order FIRST, and break ties on zone_id.
    #
    # This is not cosmetic. percentile_rank() resolves equal values by their position in the
    # list it is handed -- one of two tied zones takes 0.0 and the other 100.0, decided by
    # whichever order the rows came back from the database in. A SELECT with no ORDER BY
    # guarantees no order at all, so the same two zones can swap between one request and the
    # next: "rank #4" would name a different zone in the afternoon than it did in the
    # morning, on identical data. Sorting on (score, id) first makes the input deterministic,
    # which is the only reason the output is.
    rows.sort(key=lambda r: (-r["absolute_score"], r["zone"].id))

    # percentile_rank() reads ascending and `rows` is descending, so it is fed and unpacked
    # backwards. That is what keeps the percentile monotonic with the rank: reversed, the
    # earlier of two tied zones is the lower-ranked one, so it takes the lower percentile and
    # rank #1 can never end up displaying a smaller number than rank #2. With no ties the
    # reversal is a no-op -- percentile_rank is order-independent on distinct values.
    spread = percentile_rank([row["absolute_score"] for row in reversed(rows)])
    for row, value in zip(rows, reversed(spread), strict=True):
        row["fusion_score"] = value

    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def _all_scored(db: Session, limit: int) -> list[dict]:
    pairs = db.execute(
        select(ZoneScore, Zone).join(Zone, ZoneScore.zone_id == Zone.id).limit(limit)
    ).all()
    return rank_zones(pairs)


@router.get("/geojson")
def national_geojson(
    limit: int = Query(default=MAX_ZONES, ge=1, le=MAX_ZONES),
    db: Session = Depends(get_db),
) -> dict:
    """The whole country in one request: every scored polygon, nationally ranked.

    The properties carry the full evidence -- the three sub-scores and the explanation --
    and not just what the map needs to colour a square. That is deliberate. The alternative
    is a lean map payload plus a separate top-N list, and then clicking a polygon outside
    that top N opens nothing, which at national scale is most of the map. One request that
    can answer every question about any zone on screen beats two that cannot.
    """
    rows = _all_scored(db, limit)
    features = [
        {
            "type": "Feature",
            "geometry": _round_coords(
                row["zone"].geojson.get("geometry", row["zone"].geojson)
            ),
            "properties": {
                "zone_id": row["zone"].id,
                "name": row["zone"].name,
                "ward": row["zone"].ward,
                "city": row["zone"].city,
                "rank": row["rank"],
                "fusion_score": row["fusion_score"],
                "absolute_score": row["absolute_score"],
                "confidence": row["score"].confidence,
                "signals_used": row["score"].signals_used,
                "satellite_score": row["score"].satellite_score,
                "billing_score": row["score"].billing_score,
                "citizen_score": row["score"].citizen_score,
                "explanation": row["score"].explanation,
            },
        }
        for row in rows
    ]
    return {
        "type": "FeatureCollection",
        # Collection-level, not per-feature: it is one number repeated 6,000 times
        # otherwise, and the dashboard only ever reads it once for the "Scored 6h ago"
        # stamp. The newest run wins -- a city reseeded an hour ago makes the national
        # view an hour old, which is the honest reading of "when was this last scored".
        "computed_at": max(
            (row["score"].computed_at for row in rows), default=None
        ),
        "zone_count": len(features),
        "city_count": len({row["zone"].city for row in rows}),
        "features": features,
    }
