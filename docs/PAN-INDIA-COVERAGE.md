# National coverage: the bulk-modelled path

Companion to [`docs/PAN-INDIA.md`](PAN-INDIA.md) (R1's per-city, real-boundary generator).
Read that one first — this document assumes its billing/NRW conclusion and does not
re-argue it. Owner: R2 (Data). Status: shipped — 510 cities, 7,076 zones, live end to end.

---

## Why a second generator, not one

`build_city_zones.py` pulls a real municipal boundary from OpenStreetMap for **one named
city at a time**. That is the right answer when the boundary exists and you are onboarding
a city for a demo. It does not scale to "every Indian city, today", for two reasons that
doc already states plainly: public Overpass rate-limits after roughly eight queries per
run, and a real admin boundary simply does not exist in OSM for every city (Varanasi,
Kochi — their own examples).

This generator answers a different question: not "what is Jaipur's exact boundary" but
"what does a defensible national map look like right now, for all 510 Indian cities over
Census 2011's Class-I threshold (population ≥ 100,000), built from data that never
rate-limits." The two are complementary, not competing — see [Handoff](#handoff-to-a-real-boundary)
below for how a city moves from one to the other.

## What's built

| Layer | Source | Real or modelled |
|---|---|---|
| City registry (510 cities, 32 states) | GeoNames India dump, CC BY 4.0 | **Real** — name, population, coordinates |
| Zone polygons (7,076 zones) | `pipelines/geo/tessellate.py` | **Modelled** — a population-derived disc, tiled; see caveat below |
| Groundwater stress (36 states/UTs) | CGWB *Dynamic Ground Water Resources of India, 2023*, Annexure-I | **Real** — cross-checked against the report's own extraction/extractable columns; 30/36 states verify exactly, 6 flagged unverified in the CSV |
| Rainfall (510 cities) | Open-Meteo / ERA5 reanalysis, fetched live | **Real** |
| Billing / NRW (7,076 zones) | `pipelines/billing/generate.py`, run against the national zone file | **Synthetic**, same CPHEEO/AMRUT-calibrated generator the MVP already uses for Jaipur — `is_synthetic=true` on every row, no new claim beyond what the MVP already makes |
| Satellite (7,076 zones, demo only) | `pipelines/geo/seed_national.py`, scored through the real `ndvi.score_batch()` pipeline | **Seeded** — fabricated NDVI numbers, real scoring math, `source="seed"` |

## The honest caveat: zones are modelled, not measured

There is no open, national, machine-readable set of ward or DMA boundaries for India.
`build_city_zones.py` solves this per city, when OSM has the boundary. At 510 cities, most
without a usable OSM relation, this generator instead derives a service-area footprint from
two numbers published for every city — its centre point and its population — documented in
full in `pipelines/geo/tessellate.py`'s module docstring:

1. **Radius** from a density model calibrated to Census/MoHUA urban density bands.
2. **Zone count** targeting ~3 km² per zone (CPHEEO's District Metered Area range).
3. **Which cells survive** — a lattice clipped to the service disc, and to the *nearest-
   city* rule where two metros' discs would otherwise overlap (a corner-wise test, not
   centre-wise — see the regression tests in `tests/test_tessellate.py` for the two real
   bugs a centre-only version has: cross-city polygon overlap, and a clipped city keeping
   its full population crammed into the few cells it won).
4. **Per-zone population and mains length**, apportioned by a density gradient from the
   city centre and CPHEEO mains-density norms.

Every one of those is a stated model, not a measurement, and every one is replaced the
moment a city hands over — or `build_city_zones.py` finds — a real boundary.

## Handoff to a real boundary

`load_zones.py` (single city) and `load_national.py` (bulk) both read plain GeoJSON with
`zone_id`/`name`/`city` properties — there is no format difference between a modelled zone
and a real one. Loading `build_city_zones.py`'s output for a city **after** this national
layer is loaded works today via `load_zones.py` against that one city, with one open seam:
the two generators use different `zone_id` schemes (`{CITY_CODE}-NNN`, e.g. `JAI-014`, here;
whatever `build_city_zones.py` assigns there), so the old modelled zones for that city are
not automatically superseded — they would need a manual purge (`load_national.py --replace`
scoped to that city) before loading the real boundary in. Worth reconciling into one scheme
before either generator's output reaches a second city, not urgent before then.

## What's *not* claimed

- **Not** real ward or DMA boundaries — see above.
- **Not** real satellite readings for any of the 7,076 zones — `source="seed"`, same as
  `backend/seed.py`'s single-city fallback, until Sentinel-2 is exported per city.
- **Not** real billing data anywhere in the country — synthetic everywhere, exactly as
  Jaipur already is.
- Groundwater stress is a **state-level** figure applied to every zone in that state, per
  CGWB's own resolution. It is not zone-level, and the API says so (`GroundwaterStress` has
  no zone_id, only `state`/`district`).

## Reproducing it

```bash
cd backend
python -m pipelines.geo.registry --out ../data/india/cities.csv
python -m pipelines.geo.build_zones --cities ../data/india/cities.csv \
    --out ../data/india/zones_india.geojson --summary-out ../data/india/city_summary.csv
python -m pipelines.geo.fetch_state_boundaries --out ../data/india/states.geojson
python -m pipelines.geo.load_national --cities ../data/india/cities.csv \
    --summary ../data/india/city_summary.csv --zones ../data/india/zones_india.geojson --replace

python -m pipelines.water.load_groundwater --csv ../data/india/groundwater_cgwb2023.csv
python -m pipelines.water.rainfall --cities ../data/india/cities.csv --out ../data/india/rainfall.csv
python -m pipelines.water.load_rainfall --csv ../data/india/rainfall.csv

python -m pipelines.geo.seed_national                      # demo satellite + citizen signals
python -m pipelines.billing.generate --zones ../data/india/zones_india.geojson \
    --out ../data/india/billing_india.csv
python -m pipelines.billing.load ../data/india/billing_india.csv

curl -X POST localhost:8000/api/fusion/run/national
```

Every step is idempotent and dialect-agnostic (Postgres in production, SQLite for the
offline-demo fallback — see `app/upsert.py`).
