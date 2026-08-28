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
    describe: (n, city) => `${n} zones in ${city}, ranked`,
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

// Name or ward, case-insensitive, whitespace-tolerant. Ward lives on the GeoJSON
// properties rather than on ScoreOut, so the caller passes it in.
export function matchesQuery(score, ward, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    score.name.toLowerCase().includes(q) ||
    score.zone_id.toLowerCase().includes(q) ||
    (ward || '').toLowerCase().includes(q)
  )
}
