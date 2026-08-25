# Satellite pipeline — R1 (Abhinav)

Turn free Sentinel-2 imagery into a `0–100` "this soil looks abnormally wet/green" score per zone.

## Flow

```
zones.geojson  →  load_zones.py  →  Earth Engine script  →  CSV export  →  load.py  →  POST /api/ingest/satellite
                     writes zones      (run manually, ~weekly)   Drive/local   normalise    writes satellite_signals
```

**MVP deliberately does NOT call GEE at request time.** Export once, import, done — see
`docs/SCOPE.md`. Live scheduled refresh is Phase 2 (P1).

## Step 0 — rebuild your database (everyone, once)

> **This branch changes the schema.** `satellite_signals` and `billing_signals` gained
> natural-key unique constraints so ingest can upsert. There is no migration tool by
> design (see `app/init_db.py`), so a database created before this branch has the tables
> but not the constraints, and every ingest will fail with
> `there is no unique or exclusion constraint matching the ON CONFLICT specification`.
>
> ```bash
> cd backend
> docker compose -f ../docker-compose.yml up -d db
> docker exec neerdrishti-db psql -U neer -d neerdrishti \
>   -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
> python -m app.init_db
> python seed.py          # offline demo data, safe to re-run
> ```

## Step 1 — load the zones (once, before anything else)

`zones` must exist in the DB before any signal can be ingested against a `zone_id`.

```bash
cd backend
python -m pipelines.satellite.load_zones ../data/samples/zones.geojson
```

Idempotent — re-run any time the geojson changes (fixed a name, added a real ward
boundary) and it upserts rather than duplicating rows. Accepts `Polygon` and
`MultiPolygon` features, so a real ward split by a river or a railway line loads fine.
Use `--dry-run` to parse and print without writing.

## Step 2 — Earth Engine setup (do this on day 1, it involves a signup queue)

1. Sign up: https://code.earthengine.google.com (free, non-commercial). Approval is not instant.
2. Open `gee_ndvi.js` in this folder in the Code Editor and hit Run — the 30 zones are
   already pasted inline (generated from `data/samples/zones.geojson`), so there's no
   asset upload to wait on. If you switch to real ward boundaries with many more/larger
   polygons, upload the geojson as a Table asset instead and swap the `zones` variable.

## Step 3 — the GEE script

`gee_ndvi.js` implements the recipe below. Window is computed relative to run date, so
re-running it weekly just slides forward — no dates to keep updating by hand.

```javascript
// Current window: median composite over the last 30 days, low cloud.
var current = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterDate(START_DATE, END_DATE)
  .filterBounds(zones)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(ndvi).median();

// Baseline: same calendar window, previous 3 years, merged before taking the median.
// This is what makes it an *anomaly* and not just "green area".
var baseline = /* median across the 1/2/3-years-ago windows -- see gee_ndvi.js */;

Export.table.toDrive({
  collection: perZone,  // current + baseline + wetness_index, reduced over each zone
  description: 'neerdrishti_ndvi',
  fileFormat: 'CSV'
});
```

`gee_ndvi.js` also computes **NDWI** (`B3`,`B8`) as `wetness_index` — a leak wets soil
before it greens it, so NDWI can lead NDVI by days.

Click Run, then go to the **Tasks** tab (top right) and click **RUN** on the export —
`Export.table.toDrive` only queues it, it doesn't start on its own.

## Step 4 — CSV columns `load.py` expects

```
zone_id,observed_on,ndvi_mean,ndvi_baseline,cloud_pct,wetness_index
Z-001,2026-08-25,0.412,0.301,7.2,0.44
```

## Step 5 — load it

```bash
python -m pipelines.satellite.load ../data/samples/ndvi_export.csv --url http://localhost:8000
```

Safe to re-run for the same `observed_on` — `/api/ingest/satellite` upserts on
`(zone_id, observed_on)` rather than duplicating rows.

## Known traps

| Trap | What to do |
|---|---|
| Rain makes the whole city green | Score **relative to the city median that same day** — `ndvi.py` already does this. City-wide bumps cancel out. |
| Clouds | Median composite over 30 days + `CLOUDY_PIXEL_PERCENTAGE < 40`. Never a single scene. During Jun-Sep monsoon even 15 days / <20 can find zero scenes over Rajasthan and `.select('ndvi')` throws "Image with no bands" (error code 3) -- that's why the window is wider than it looks like it needs to be. |
| Farmland / parks look like permanent leaks | Baseline is the same calendar window in prior years, so a park that's always green has ~0 anomaly. |
| Zone too big | ~1–2 km cells. A 10 km ward averages the leak away. |
| GEE quota / export slowness | Export to Drive, not `getInfo()`. Start the export and go work on something else. |
