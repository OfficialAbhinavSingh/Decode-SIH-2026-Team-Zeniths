# Satellite pipeline — R1 (Abhinav)

Turn free Sentinel-2 imagery into a `0–100` "this soil looks abnormally wet/green" score per zone.

## Flow

```
Google Earth Engine script  →  CSV export  →  load.py  →  POST /api/ingest/satellite
   (run manually, ~weekly)      Drive/local    normalise      writes satellite_signals
```

**MVP deliberately does NOT call GEE at request time.** Export once, import, done — see
`docs/SCOPE.md`. Live scheduled refresh is Phase 2 (P1).

## Step 1 — Earth Engine setup (do this on day 1, it involves a signup queue)

1. Sign up: https://code.earthengine.google.com (free, non-commercial). Approval is not instant.
2. Upload `data/samples/zones.geojson` as an asset, or paste the FeatureCollection inline.

## Step 2 — the GEE script

Pseudocode of what `gee_ndvi.js` must do (keep the real script in this folder):

```javascript
var zones = ee.FeatureCollection('users/<you>/neerdrishti_zones');

function ndvi(img) {
  return img.normalizedDifference(['B8', 'B4']).rename('ndvi');
}

// Current window: median composite over ~15 days, low cloud.
var current = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterDate('2026-08-10', '2026-08-25')
  .filterBounds(zones)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .map(ndvi).median();

// Baseline: same calendar window, previous 3 years. This is what makes it an *anomaly*
// and not just "green area".
var baseline = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filter(ee.Filter.or(
    ee.Filter.date('2023-08-10', '2023-08-25'),
    ee.Filter.date('2024-08-10', '2024-08-25'),
    ee.Filter.date('2025-08-10', '2025-08-25')))
  .filterBounds(zones)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
  .map(ndvi).median();

var anomaly = current.subtract(baseline).rename('ndvi_anomaly');

Export.table.toDrive({
  collection: current.addBands(baseline).addBands(anomaly)
    .reduceRegions({collection: zones, reducer: ee.Reducer.mean(), scale: 10}),
  description: 'neerdrishti_ndvi',
  fileFormat: 'CSV'
});
```

Optional second band worth adding if time allows: **NDWI** (`B3`,`B8`) as `wetness_index` —
a leak wets soil before it greens it, so NDWI can lead NDVI by days.

## Step 3 — CSV columns `load.py` expects

```
zone_id,observed_on,ndvi_mean,ndvi_baseline,cloud_pct,wetness_index
Z-001,2026-08-25,0.412,0.301,7.2,0.44
```

## Step 4 — load it

```bash
python -m pipelines.satellite.load data/samples/ndvi_export.csv --url http://localhost:8000
```

## Known traps

| Trap | What to do |
|---|---|
| Rain makes the whole city green | Score **relative to the city median that same day** — `ndvi.py` already does this. City-wide bumps cancel out. |
| Clouds | Median composite over 15 days + `CLOUDY_PIXEL_PERCENTAGE < 20`. Never a single scene. |
| Farmland / parks look like permanent leaks | Baseline is the same calendar window in prior years, so a park that's always green has ~0 anomaly. |
| Zone too big | ~1–2 km cells. A 10 km ward averages the leak away. |
| GEE quota / export slowness | Export to Drive, not `getInfo()`. Start the export and go work on something else. |
