// One place for every backend call. In dev, Vite proxies /api to localhost:8000.
// In production, VITE_API_URL points at the Render web service.
const BASE = import.meta.env.VITE_API_URL || ''

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${path} -> ${res.status}`)
  return res.json()
}

export const getScores = (city, limit) => {
  const q = new URLSearchParams()
  if (city) q.set('city', city)
  if (limit) q.set('limit', limit)
  return get(`/api/scores?${q}`)
}

export const getScoresGeojson = (city) =>
  get(`/api/scores/geojson${city ? `?city=${encodeURIComponent(city)}` : ''}`)

export const getZoneSignals = (zoneId) => get(`/api/zones/${zoneId}/signals`)

export const getZone = (zoneId) => get(`/api/zones/${zoneId}`)

// The dashboard scores only reports that fall inside a mapped zone, so it also has to be
// able to show the ones it did not score. This returns them all, newest first, including
// the zone_id=null ones the fusion engine deliberately ignores.
export const getReports = (limit = 8) => get(`/api/reports?limit=${limit}`)

// --- National coverage -------------------------------------------------------
// Three levels of detail, matching the three zoom levels of the map. Returning the
// wrong shape of response for a zoom level is not fixable in the client, so each has
// its own endpoint -- see backend/app/routers/national.py.

export const getNationalSummary = () => get('/api/national/summary')

export const getStateRollup = () => get('/api/national/states')

export const getCityRollup = (params = {}) => {
  const q = new URLSearchParams()
  if (params.state) q.set('state', params.state)
  if (params.limit) q.set('limit', params.limit)
  if (params.minPriority) q.set('min_priority', params.minPriority)
  return get(`/api/national/cities?${q}`)
}

export const getCityDetail = (cityCode) => get(`/api/national/cities/${cityCode}`)

export const getScoresByCityCode = (cityCode, limit) => {
  const q = new URLSearchParams({ city_code: cityCode })
  if (limit) q.set('limit', limit)
  return get(`/api/scores?${q}`)
}

export const getScoresGeojsonByCityCode = (cityCode) =>
  get(`/api/scores/geojson?city_code=${encodeURIComponent(cityCode)}`)

// The simplified state boundary layer used by the national choropleth. Served as a
// static asset (frontend/public/data/states.geojson) rather than by the API: it never
// changes at runtime, and shipping it as a file lets the CDN cache it instead of the
// API re-serving the same 0.7 MB on every page load.
export const getStateBoundaries = () => fetch('/data/states.geojson').then((r) => r.json())

export async function submitReport(body) {
  const res = await fetch(`${BASE}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'report failed')
  return res.json()
}
