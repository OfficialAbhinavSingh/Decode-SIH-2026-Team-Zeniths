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

// Which cities actually have zones loaded. Derived server-side from the zones table, so
// a database holding only the seeded Jaipur grid returns exactly one row and the picker
// hides itself -- the dashboard looks and behaves the way it always has.
export const getCities = () => get('/api/cities')

// Every scored zone in the country in one FeatureCollection, ranked against each other
// rather than within their own city. One request rather than a lean map payload plus a
// top-N list: at national scale most of what is on screen falls outside any top N, and a
// polygon you can see but cannot open is worse than a slightly larger download. The
// backend gzips it (~340 KB on the wire for 6,000 zones).
export const getNationalGeojson = () => get('/api/national/geojson')

export const getZoneSignals = (zoneId) => get(`/api/zones/${zoneId}/signals`)

export const getZone = (zoneId) => get(`/api/zones/${zoneId}`)

// The dashboard scores only reports that fall inside a mapped zone, so it also has to be
// able to show the ones it did not score. This returns them all, newest first, including
// the zone_id=null ones the fusion engine deliberately ignores.
export const getReports = (limit = 8) => get(`/api/reports?limit=${limit}`)

export async function submitReport(body) {
  const res = await fetch(`${BASE}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'report failed')
  return res.json()
}
