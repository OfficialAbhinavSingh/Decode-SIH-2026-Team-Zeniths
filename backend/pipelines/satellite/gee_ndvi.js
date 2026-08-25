/**
 * NeerDrishti -- Sentinel-2 NDVI anomaly export (R1, satellite pipeline).
 *
 * Run this in the Earth Engine Code Editor (https://code.earthengine.google.com).
 * It is meant to be re-run manually, roughly weekly -- see pipelines/satellite/README.md.
 *
 * Output: one CSV row per zone with ndvi_mean / ndvi_baseline / wetness_index, ready for
 *   python -m pipelines.satellite.load <exported.csv>
 *
 * Zones are pasted inline below rather than uploaded as an EE asset -- 30 small polygons
 * are well under the script-size limit and this avoids the asset-upload/ingestion wait.
 * If you switch to real ward boundaries with many more/larger polygons, upload
 * data/samples/zones.geojson as a Table asset instead and replace `zones` below with
 * ee.FeatureCollection('users/<you>/neerdrishti_zones').
 */

var zones = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Polygon([[[75.7453, 26.8764], [75.7573, 26.8764], [75.7573, 26.8884], [75.7453, 26.8884], [75.7453, 26.8764]]]), {zone_id: 'Z-001'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7573, 26.8764], [75.7693, 26.8764], [75.7693, 26.8884], [75.7573, 26.8884], [75.7573, 26.8764]]]), {zone_id: 'Z-002'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7693, 26.8764], [75.7813, 26.8764], [75.7813, 26.8884], [75.7693, 26.8884], [75.7693, 26.8764]]]), {zone_id: 'Z-003'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7813, 26.8764], [75.7933, 26.8764], [75.7933, 26.8884], [75.7813, 26.8884], [75.7813, 26.8764]]]), {zone_id: 'Z-004'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7933, 26.8764], [75.8053, 26.8764], [75.8053, 26.8884], [75.7933, 26.8884], [75.7933, 26.8764]]]), {zone_id: 'Z-005'}),
  ee.Feature(ee.Geometry.Polygon([[[75.8053, 26.8764], [75.8173, 26.8764], [75.8173, 26.8884], [75.8053, 26.8884], [75.8053, 26.8764]]]), {zone_id: 'Z-006'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7453, 26.8884], [75.7573, 26.8884], [75.7573, 26.9004], [75.7453, 26.9004], [75.7453, 26.8884]]]), {zone_id: 'Z-007'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7573, 26.8884], [75.7693, 26.8884], [75.7693, 26.9004], [75.7573, 26.9004], [75.7573, 26.8884]]]), {zone_id: 'Z-008'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7693, 26.8884], [75.7813, 26.8884], [75.7813, 26.9004], [75.7693, 26.9004], [75.7693, 26.8884]]]), {zone_id: 'Z-009'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7813, 26.8884], [75.7933, 26.8884], [75.7933, 26.9004], [75.7813, 26.9004], [75.7813, 26.8884]]]), {zone_id: 'Z-010'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7933, 26.8884], [75.8053, 26.8884], [75.8053, 26.9004], [75.7933, 26.9004], [75.7933, 26.8884]]]), {zone_id: 'Z-011'}),
  ee.Feature(ee.Geometry.Polygon([[[75.8053, 26.8884], [75.8173, 26.8884], [75.8173, 26.9004], [75.8053, 26.9004], [75.8053, 26.8884]]]), {zone_id: 'Z-012'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7453, 26.9004], [75.7573, 26.9004], [75.7573, 26.9124], [75.7453, 26.9124], [75.7453, 26.9004]]]), {zone_id: 'Z-013'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7573, 26.9004], [75.7693, 26.9004], [75.7693, 26.9124], [75.7573, 26.9124], [75.7573, 26.9004]]]), {zone_id: 'Z-014'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7693, 26.9004], [75.7813, 26.9004], [75.7813, 26.9124], [75.7693, 26.9124], [75.7693, 26.9004]]]), {zone_id: 'Z-015'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7813, 26.9004], [75.7933, 26.9004], [75.7933, 26.9124], [75.7813, 26.9124], [75.7813, 26.9004]]]), {zone_id: 'Z-016'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7933, 26.9004], [75.8053, 26.9004], [75.8053, 26.9124], [75.7933, 26.9124], [75.7933, 26.9004]]]), {zone_id: 'Z-017'}),
  ee.Feature(ee.Geometry.Polygon([[[75.8053, 26.9004], [75.8173, 26.9004], [75.8173, 26.9124], [75.8053, 26.9124], [75.8053, 26.9004]]]), {zone_id: 'Z-018'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7453, 26.9124], [75.7573, 26.9124], [75.7573, 26.924400000000002], [75.7453, 26.924400000000002], [75.7453, 26.9124]]]), {zone_id: 'Z-019'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7573, 26.9124], [75.7693, 26.9124], [75.7693, 26.924400000000002], [75.7573, 26.924400000000002], [75.7573, 26.9124]]]), {zone_id: 'Z-020'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7693, 26.9124], [75.7813, 26.9124], [75.7813, 26.924400000000002], [75.7693, 26.924400000000002], [75.7693, 26.9124]]]), {zone_id: 'Z-021'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7813, 26.9124], [75.7933, 26.9124], [75.7933, 26.924400000000002], [75.7813, 26.924400000000002], [75.7813, 26.9124]]]), {zone_id: 'Z-022'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7933, 26.9124], [75.8053, 26.9124], [75.8053, 26.924400000000002], [75.7933, 26.924400000000002], [75.7933, 26.9124]]]), {zone_id: 'Z-023'}),
  ee.Feature(ee.Geometry.Polygon([[[75.8053, 26.9124], [75.8173, 26.9124], [75.8173, 26.924400000000002], [75.8053, 26.924400000000002], [75.8053, 26.9124]]]), {zone_id: 'Z-024'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7453, 26.924400000000002], [75.7573, 26.924400000000002], [75.7573, 26.936400000000003], [75.7453, 26.936400000000003], [75.7453, 26.924400000000002]]]), {zone_id: 'Z-025'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7573, 26.924400000000002], [75.7693, 26.924400000000002], [75.7693, 26.936400000000003], [75.7573, 26.936400000000003], [75.7573, 26.924400000000002]]]), {zone_id: 'Z-026'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7693, 26.924400000000002], [75.7813, 26.924400000000002], [75.7813, 26.936400000000003], [75.7693, 26.936400000000003], [75.7693, 26.924400000000002]]]), {zone_id: 'Z-027'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7813, 26.924400000000002], [75.7933, 26.924400000000002], [75.7933, 26.936400000000003], [75.7813, 26.936400000000003], [75.7813, 26.924400000000002]]]), {zone_id: 'Z-028'}),
  ee.Feature(ee.Geometry.Polygon([[[75.7933, 26.924400000000002], [75.8053, 26.924400000000002], [75.8053, 26.936400000000003], [75.7933, 26.936400000000003], [75.7933, 26.924400000000002]]]), {zone_id: 'Z-029'}),
  ee.Feature(ee.Geometry.Polygon([[[75.8053, 26.924400000000002], [75.8173, 26.924400000000002], [75.8173, 26.936400000000003], [75.8053, 26.936400000000003], [75.8053, 26.924400000000002]]]), {zone_id: 'Z-030'})
]);

// Rolling 15-day window ending today. Re-running this script later automatically
// slides the window forward -- no hardcoded dates to go stale.
var END_DATE = ee.Date(Date.now());
var START_DATE = END_DATE.advance(-15, 'day');
var CLOUD_MAX = 20; // CLOUDY_PIXEL_PERCENTAGE threshold from the README's "known traps"

function withIndices(img) {
  var ndvi = img.normalizedDifference(['B8', 'B4']).rename('ndvi');
  var ndwi = img.normalizedDifference(['B3', 'B8']).rename('ndwi'); // wetness_index
  return img.addBands([ndvi, ndwi]);
}

function median(start, end) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterDate(start, end)
    .filterBounds(zones)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', CLOUD_MAX))
    .map(withIndices)
    .median();
}

var current = median(START_DATE, END_DATE);

// Baseline: same calendar window, previous 3 years, merged into one collection before
// taking the median. This is what makes the score an *anomaly* and not just "green area" --
// see the README's rain and farmland traps.
var baselineCollection = ee.ImageCollection([]);
for (var yearsAgo = 1; yearsAgo <= 3; yearsAgo++) {
  var win = median(START_DATE.advance(-yearsAgo, 'year'), END_DATE.advance(-yearsAgo, 'year'));
  baselineCollection = baselineCollection.merge(ee.ImageCollection([win]));
}
var baseline = baselineCollection.median();

var combined = current.select(['ndvi', 'ndwi'], ['ndvi_mean', 'wetness_index'])
  .addBands(baseline.select('ndvi').rename('ndvi_baseline'));

var perZone = combined.reduceRegions({
  collection: zones,
  reducer: ee.Reducer.mean(),
  scale: 10
});

// Stamp the export date and drop the geometry column -- load.py only needs the properties.
perZone = perZone.map(function (f) {
  return f.set('observed_on', END_DATE.format('YYYY-MM-dd')).setGeometry(null);
});

Export.table.toDrive({
  collection: perZone,
  description: 'neerdrishti_ndvi',
  fileFormat: 'CSV',
  selectors: ['zone_id', 'observed_on', 'ndvi_mean', 'ndvi_baseline', 'wetness_index']
});
