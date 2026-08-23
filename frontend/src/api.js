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

export async function submitReport(body) {
  const res = await fetch(`${BASE}/api/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'report failed')
  return res.json()
}
