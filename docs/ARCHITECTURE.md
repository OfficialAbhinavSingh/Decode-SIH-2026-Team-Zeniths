# Architecture

## The whole system on one screen

```
   ┌── SOURCES ─────────────┐   ┌── PIPELINES ────────┐   ┌── CORE ───────┐   ┌── OUT ──────┐

   Sentinel-2 (free)   ───►  pipelines/satellite/  ──┐
   via Google Earth Engine    NDVI vs 3-yr baseline  │
                              → score 0-100          │
                                                     │
   Municipal billing   ───►  pipelines/billing/    ──┤    ┌───────────┐      React + Leaflet
   (synthetic, CPHEEO-        NRW gap %              ├──► │  Postgres │ ───► map dashboard
    benchmarked)              → score 0-100          │    │  (5 tbls) │      ranked repair list
                                                     │    └─────┬─────┘      zone detail + "why"
   Citizens on WhatsApp ──►  n8n workflow          ──┘          │
                              parse + dedupe +                  ▼
                              zone-match             ┌──────────────────────┐
                              → POST /api/reports    │  fusion.py           │
                                                     │  weighted avg over   │
                                                     │  present signals     │──► zone_scores
                                                     │  + confidence        │    (rank, explanation)
                                                     │  + explanation       │
                                                     └──────────────────────┘
```

**One sentence:** three cheap signals → one score per zone → a ranked list of where to dig.

---

## Why this shape

| Decision | Reason |
|---|---|
| Signals are **independent producers** that only write rows | 3 people work in parallel, zero merge conflicts, any signal can be missing without breaking the system |
| Fusion is a **pure function over the DB**, not a stream | Re-runnable, testable, demoable. `POST /api/fusion/run` any time. |
| Scores normalised to `0–100` at the **producer**, not the consumer | Fusion never needs to know NDVI from kilolitres |
| Missing signal ⇒ **renormalise weights** | Real cities have partial data. Handling this is the honest-engineering point in the pitch. |
| `explanation` string generated in fusion | The dashboard's most important pixel is a sentence, not a number |
| GeoJSON in JSONB, no PostGIS | Nothing in MVP needs spatial SQL; PostGIS setup risk removed |

## Request flow — the demo path

1. `POST /api/fusion/run?city=X` (or the Render background worker cron)
2. Fusion reads latest `satellite_signals`, `billing_signals`, and a rolling 30-day count of
   `citizen_reports` per zone
3. Writes `zone_scores` with `rank` + `explanation`
4. Dashboard calls `GET /api/scores/geojson` → colours the map in one request
5. Judge clicks a red zone → `GET /api/zones/Z-014/signals` → the three bars + the reports

## Stack

| Layer | Choice | Note |
|---|---|---|
| API | FastAPI (Python 3.11+) | same language as the geo/data pipelines |
| DB | PostgreSQL 16 | Render managed in prod, docker-compose locally |
| ORM | SQLAlchemy 2 | |
| Frontend | React + Vite + Leaflet | Leaflet over Mapbox: no API key, no billing |
| Automation | n8n | WhatsApp intake, cron, alerts — sponsor track |
| AI assist | Lyzr / Gemini | Phase 2 only: plain-language crew brief |
| Deploy | Render | Web Service + Postgres + Static Site + Worker |

## Deployment (Render, 4 services)

```
neerdrishti-api      Web Service     backend/     uvicorn app.main:app
neerdrishti-db       PostgreSQL      —            free tier
neerdrishti-web      Static Site     frontend/    npm run build → dist/
neerdrishti-fusion   Background Worker            cron → POST /api/fusion/run
```

## Security / privacy notes (judges ask this)

- Phone numbers from WhatsApp are **hashed before storage** (`reporter_hash`). Raw numbers never
  hit the DB.
- Billing data is synthetic and flagged `is_synthetic=true` in every row.
- No auth in MVP — the dashboard is read-only public data. Ingest endpoints take a shared
  `INGEST_TOKEN` header so a stranger can't poison the map.
