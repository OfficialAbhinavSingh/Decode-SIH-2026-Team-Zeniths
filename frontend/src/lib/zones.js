// Shared zone maths used by both the list and the map, so a zone can never be filtered
// into the list but left off the map (or the reverse).

// Green (safe) -> red (inspect first). Fusion scores are percentile-ranked within the city
// by the backend, so this ramp always uses its full range instead of collapsing to one hue.
export function scoreColor(score) {
  if (score >= 80) return '#d9342b'
  if (score >= 60) return '#f0603c'
  if (score >= 40) return '#e0a032'
  if (score >= 20) return '#a8b23c'
  return '#3f9a63'
}

// The first coordinate ring of a Polygon, or of the first Polygon in a MultiPolygon.
function outerRing(geometry) {
  if (!geometry) return null
  if (geometry.type === 'Polygon') return geometry.coordinates?.[0] || null
  if (geometry.type === 'MultiPolygon') return geometry.coordinates?.[0]?.[0] || null
  return null
}

// Vertex average, not the true area centroid. Our zones are grid rectangles, so the two
// agree; for an irregular ward it stays inside the polygon, which is all a pin needs.
export function centroidOf(geometry) {
  const ring = outerRing(geometry)
  if (!ring || ring.length === 0) return null
  let lat = 0
  let lon = 0
  for (const [x, y] of ring) {
    lon += x
    lat += y
  }
  return [lat / ring.length, lon / ring.length]
}

// GeoJSON is [lon, lat]; Leaflet wants [lat, lon]. Getting this backwards puts Jaipur
// in the Indian Ocean, so it lives in one function.
export function firstVertexLatLon(geometry) {
  const ring = outerRing(geometry)
  if (!ring || ring.length === 0) return null
  return [ring[0][1], ring[0][0]]
}

// The sentinel `city` value meaning "the whole country, ranked against itself" rather
// than any one city. Not a real city name, and deliberately not one that could ever be
// mistaken for one: it is compared against `Zone.city` values on the way to the API, and a
// plausible name like "India" would silently become a ?city= filter matching nothing.
export const NATIONAL = '__india__'

export const SIGNAL_KEYS = ['satellite_score', 'billing_score', 'citizen_score']

// How far apart this zone's available signals are. Two signals at 95 and 20 mean the
// evidence is contested and a crew should verify before digging; two signals at 88 and 84
// mean they corroborate. Null when fewer than two signals exist -- one signal cannot
// disagree with anything, and that is different from agreeing.
export function signalSpread(score) {
  const present = SIGNAL_KEYS.map((k) => score[k]).filter((v) => v !== null && v !== undefined)
  if (present.length < 2) return null
  return Math.max(...present) - Math.min(...present)
}

// Score at or above the legend's top bucket -- the same threshold the map colours red,
// so "Inspect first" in the filter and "Inspect first" in the legend mean one thing.
export const INSPECT_FIRST_MIN = 80
export const DISAGREEMENT_MIN = 40

export const FILTERS = {
  all: {
    label: 'All zones',
    describe: (n, scope) => `${n} zones in ${scope}, ranked`,
    test: () => true,
  },
  inspect: {
    label: 'Inspect first',
    describe: (n) => `${n} zones scoring ${INSPECT_FIRST_MIN}+`,
    test: (s) => s.fusion_score >= INSPECT_FIRST_MIN,
  },
  disagreeing: {
    label: 'Disagreeing',
    describe: (n) => `${n} zones where signals disagree by ${DISAGREEMENT_MIN}+ points`,
    test: (s) => {
      const spread = signalSpread(s)
      return spread !== null && spread >= DISAGREEMENT_MIN
    },
  },
}

// Name, zone id, ward or city -- case-insensitive, whitespace-tolerant. Ward lives on the
// GeoJSON properties rather than on ScoreOut, so the caller passes it in.
//
// City only exists on the national rows, and typing a city name is the first thing anyone
// does to a map of the whole country. In a single-city view it is absent and the clause
// costs nothing; matching it there would only match everything anyway.
export function matchesQuery(score, ward, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    score.name.toLowerCase().includes(q) ||
    score.zone_id.toLowerCase().includes(q) ||
    (ward || '').toLowerCase().includes(q) ||
    (score.city || '').toLowerCase().includes(q)
  )
}

// ---------------------------------------------------------------- point in zone
//
// A deliberate port of backend/app/services/geo.py, down to the strict `<` in the
// crossing test. The report form uses it to tell someone which zone their pin falls in
// *before* they submit, and the backend re-runs its own copy on the point it receives.
// Two implementations of one rule can disagree on a boundary pixel, so the form must
// treat this as a preview and never as the verdict -- the answer that reaches the
// resident is still the zone_id in the API response.
function ringContains(lon, lat, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > lat !== yj > lat) {
      const xAtLat = ((xj - xi) * (lat - yi)) / (yj - yi) + xi
      if (lon < xAtLat) inside = !inside
    }
  }
  return inside
}

/** True if [lat, lon] falls inside a GeoJSON Polygon or MultiPolygon, holes respected. */
export function pointInGeometry(lat, lon, geometry) {
  if (!geometry) return false
  if (geometry.type === 'Feature') return pointInGeometry(lat, lon, geometry.geometry)
  const coords = geometry.coordinates
  if (!coords) return false
  const polygons =
    geometry.type === 'Polygon' ? [coords] : geometry.type === 'MultiPolygon' ? coords : null
  if (!polygons) return false
  for (const polygon of polygons) {
    if (!polygon || !polygon[0]) continue
    if (!ringContains(lon, lat, polygon[0])) continue
    const inHole = polygon.slice(1).some((hole) => ringContains(lon, lat, hole))
    if (!inHole) return true
  }
  return false
}

/** The first zone feature containing the point, or null. Mirrors match_zone() server-side. */
export function zoneAt(lat, lon, geojson) {
  for (const feature of geojson?.features || []) {
    if (pointInGeometry(lat, lon, feature.geometry)) return feature.properties
  }
  return null
}

// ------------------------------------------------- decoding the headline score
//
// `fusion_score` is not a magnitude. fusion.py computes a weighted score, discounts it for
// coverage, and then replaces it with the zone's *percentile within the city* -- without
// that spread every zone lands in the 55-65 band and the map is one flat colour.
//
// The cost is a panel where a zone with one signal at 86 shows a headline of 90, and both
// numbers are percentiles of different populations: the sub-scores are percentile-ranked
// within their own signal (billing does this in pipelines/billing/load.py), the headline is
// percentile-ranked across fused scores. Reading 90 as "90 out of 100" is then the natural
// mistake, and it is the first thing anyone asks about.
//
// So we recompute the magnitude the percentile came from and show it. These two constants
// mirror fusion.py, which stores only the percentile and discards the raw value.
// **fusion.py is the source of truth** -- if WEIGHTS or COVERAGE_FACTOR change there,
// change them here in the same PR or this line quietly starts lying.
const FUSION_WEIGHTS = { satellite_score: 0.4, billing_score: 0.35, citizen_score: 0.25 }
const FUSION_COVERAGE = { 0: 0, 1: 0.7, 2: 0.9, 3: 1 }

/** The weighted, coverage-discounted score behind the percentile, or null if no signal. */
export function rawFusedScore(score) {
  const present = Object.entries(FUSION_WEIGHTS).filter(
    ([key]) => score[key] !== null && score[key] !== undefined,
  )
  if (present.length === 0) return null
  const weightSum = present.reduce((sum, [, w]) => sum + w, 0)
  const weighted = present.reduce((sum, [key, w]) => sum + w * score[key], 0) / weightSum
  return weighted * FUSION_COVERAGE[present.length]
}
