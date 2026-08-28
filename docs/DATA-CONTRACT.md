# Data contract — FROZEN

This is the single thing all 6 lanes agree on. Everything else is private to a lane.

**Changing anything here requires telling the whole team first.** Owner: R3 (Backend & Fusion).

Conventions:
- Every score is `0–100`, higher = more suspicious. Never `None` inside a score; a missing signal
  means **no row**, not a row with `0`.
- All timestamps UTC, ISO-8601.
- `zone_id` is the join key for everything. It comes from R1's `zones.geojson` (`properties.zone_id`).
- Geometry is plain GeoJSON in a `JSONB` column. **No PostGIS.** No spatial queries in MVP.

---

## Tables

### `zones` — owned by R1
| column | type | notes |
|---|---|---|
| `id` | text PK | e.g. `Z-014`, from geojson `properties.zone_id` |
| `name` | text | `"Ward 7 – Sector 3"` |
| `city` | text | |
| `ward` | text | nullable |
| `centroid_lat` | float | for map fly-to |
| `centroid_lon` | float | |
| `geojson` | jsonb | the polygon |
| `pipe_length_km` | float | nullable; used to normalise NRW |
| `population` | int | nullable |
| `created_at` | timestamptz | |

### `satellite_signals` — written by R1
| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `zone_id` | text FK | |
| `observed_on` | date | end of the composite window |
| `ndvi_mean` | float | this window |
| `ndvi_baseline` | float | median of same window, prior 2–3 years |
| `ndvi_anomaly` | float | `mean - baseline` |
| `wetness_index` | float | nullable (NDWI / soil moisture proxy) |
| `cloud_pct` | float | nullable; QA field |
| `score` | float | **0–100**, computed by R1 |
| `source` | text | `"sentinel2-gee"` or `"seed"` |

### `billing_signals` — written by R2
| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `zone_id` | text FK | |
| `period_start` / `period_end` | date | |
| `supplied_kl` | float | kilolitres into the zone |
| `billed_kl` | float | kilolitres billed to consumers |
| `nrw_pct` | float | `(supplied-billed)/supplied*100` |
| `score` | float | **0–100**, computed by R2 |
| `is_synthetic` | bool | **default true.** Do not lie about this. |

### `citizen_reports` — written by R5
| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `zone_id` | text FK | nullable if we couldn't match a zone |
| `reported_at` | timestamptz | |
| `channel` | text | `whatsapp` / `web` / `telegram` |
| `reporter_hash` | text | hashed phone. **Never store a raw phone number.** |
| `description` | text | |
| `lat` / `lon` | float | nullable |
| `media_url` | text | nullable |
| `status` | text | `new` / `verified` / `dismissed` |

### `zone_scores` — written by R3 (fusion output)
| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `zone_id` | text FK | |
| `computed_at` | timestamptz | |
| `satellite_score` | float | nullable |
| `billing_score` | float | nullable |
| `citizen_score` | float | nullable |
| `fusion_score` | float | **0–100** |
| `confidence` | text | `low` / `medium` / `high` |
| `signals_used` | int | 1–3 |
| `rank` | int | 1 = inspect first |
| `explanation` | text | human sentence shown in the UI |

---

## API

Base: `/api`. All responses JSON. Errors: `{"detail": "..."}` with the right HTTP code.

| Method | Path | Who calls it | Returns |
|---|---|---|---|
| `GET` | `/health` | R6 | `{"status":"ok","db":true}` |
| `GET` | `/api/zones?city=` | R4 | `Zone[]` |
| `GET` | `/api/zones/{zone_id}` | R4 | `Zone` |
| `GET` | `/api/zones/{zone_id}/signals` | R4 | `{satellite:[], billing:[], citizen:[]}` |
| `GET` | `/api/scores?city=&limit=` | R4 | `ZoneScore[]`, sorted by `rank` |
| `GET` | `/api/scores/geojson?city=` | R4 | FeatureCollection, each feature has `fusion_score` in properties — **map draws straight from this** |
| `POST` | `/api/reports` | R5 | creates a `citizen_reports` row |
| `POST` | `/api/ingest/satellite` | R1 | bulk upsert `SatelliteSignal[]` |
| `POST` | `/api/ingest/billing` | R2 | bulk upsert `BillingSignal[]` |
| `POST` | `/api/fusion/run?city=` | R3 / cron | recomputes all `zone_scores`, returns `{"zones_scored": n}` |

### `POST /api/reports` body
```json
{
  "channel": "whatsapp",
  "reporter_hash": "sha256:ab12...",
  "description": "Water leaking near the school gate for 3 days",
  "lat": 26.9124,
  "lon": 75.7873,
  "zone_id": null,
  "media_url": null
}
```
Either `zone_id` **or** `lat`+`lon` must be present. If only lat/lon, the API point-in-polygon
matches it to a zone.

### `GET /api/scores` item
```json
{
  "zone_id": "Z-014",
  "name": "Ward 7 – Sector 3",
  "rank": 1,
  "fusion_score": 87.4,
  "confidence": "high",
  "signals_used": 3,
  "satellite_score": 91.2,
  "billing_score": 84.0,
  "citizen_score": 78.5,
  "explanation": "NDVI 0.18 above 3-year baseline, 41% non-revenue water, and 4 citizen reports in 10 days — all three signals agree.",
  "computed_at": "2026-08-30T04:00:00Z"
}
```

---

## Fusion rule (R3 owns; written here so everyone can defend it on stage)

```
weights  = {satellite: 0.40, billing: 0.35, citizen: 0.25}
coverage = {1 signal: 0.70, 2 signals: 0.90, 3 signals: 1.00}

present = signals that actually have a row for this zone
mean         = sum(w[s] * score[s] for s in present) / sum(w[s] for s in present)
fusion_score = mean * coverage[len(present)]
```

Missing signal ⇒ **weights renormalise**. A zone with only a satellite signal is scored on satellite
alone, not penalised to 40% of its score.

Then ⇒ **coverage discount**. Renormalising alone made one unverified reading of 86 score exactly
what three sources agreeing at 86 score, and percentile-ranking pushed whichever was highest to 100.
With the real Sentinel-2 export loaded, three of the top six zones were single-signal leads and the
only zone carrying all three signals sat at rank 5. Coverage is a multiplier, not a veto: a lone
satellite reading of 90 lands at **63** — not 36, which is what refusing to renormalise would give
it, and not 90. A lead stays on the list; it just cannot outrank corroboration.

```
confidence = high   if signals_used == 3 and max-min spread <= 25
             medium if signals_used >= 2
             low    if signals_used == 1
```

Scores are **percentile-ranked within the city** before display, so the map actually has colour
spread instead of everything sitting at 60.
