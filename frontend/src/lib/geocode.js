// Place search for the citizen report form.
//
// Google Places was the obvious first thought and is the wrong pick here. It needs a billed
// API key in the client bundle, and this repo has already been burned once by a keyed map
// service: the CARTO basemap in MapView.jsx rendered as a tiled "API KEY REQUIRED"
// watermark at exactly the zoom levels used on stage. Nominatim is the search side of the
// same OpenStreetMap data the map already draws, needs no key, and cannot start failing
// because a billing alert fired the night before the demo.
//
// Swapping providers later is a two-value change, not a rewrite -- point VITE_GEOCODER_URL
// at any service whose search endpoint takes ?q= and returns [{lat, lon, display_name}],
// which Nominatim-compatible servers (Photon, a self-hosted instance, MapTiler's Nominatim
// mode) all do.
const BASE = import.meta.env.VITE_GEOCODER_URL || 'https://nominatim.openstreetmap.org'

// Greater Jaipur -- deliberately wider than the monitored zones, so Amer and Sanganer are
// reachable even though no zone covers them yet.
//
// A viewbox on its own is only a ranking hint, and a weak one: measured against the live
// API, "MI Road" with an unbounded viewbox returned Mile Road in London first and Nathan
// Road in Hong Kong second, with nothing in Jaipur in the top three. bounded=1 is what
// actually restricts, and it fixes that query -- but it is a hard filter, and it turned
// "Amer Fort" into zero results when the box was drawn tight around the zones.
//
// Hence two passes, in searchPlaces(): bounded first so local places win, then a global
// retry only when the local pass finds nothing. Somewhere genuinely far away stays
// reachable, which matters because the backend logs an out-of-coverage point honestly
// rather than rejecting it -- the search must be able to reach one.
const VIEWBOX = '75.55,27.12,76.10,26.65'

// Nominatim's usage policy caps this at one request per second per application. The 450ms
// debounce in LocationSearch plus a 3-character minimum keeps a normal typist under that;
// a shared demo laptop is nowhere near it.
export const MIN_QUERY = 3
export const DEBOUNCE_MS = 450

// Nominatim's display_name is the full administrative chain -- "Ashok Nagar, Ward 61,
// Jaipur, Rajasthan, 302001, India". The head is what the resident recognises; the tail
// disambiguates two roads with the same name. Splitting them lets the dropdown show the
// first line big and the rest small instead of one truncated run-on.
function splitLabel(displayName) {
  const parts = String(displayName || '').split(',').map((s) => s.trim()).filter(Boolean)
  if (parts.length === 0) return { title: 'Unnamed place', detail: '' }
  return { title: parts[0], detail: parts.slice(1).join(', ') }
}

function toPlace(raw) {
  const lat = Number.parseFloat(raw.lat)
  const lon = Number.parseFloat(raw.lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return {
    id: `${raw.osm_type || 'x'}${raw.osm_id || `${lat},${lon}`}`,
    lat,
    lon,
    ...splitLabel(raw.display_name),
  }
}

async function runSearch(q, bounded, signal) {
  const params = new URLSearchParams({
    q,
    format: 'jsonv2',
    limit: '6',
    viewbox: VIEWBOX,
    'accept-language': 'en',
  })
  if (bounded) params.set('bounded', '1')
  const res = await fetch(`${BASE}/search?${params}`, { signal })
  if (!res.ok) throw new Error(`Place search unavailable (${res.status})`)
  const body = await res.json()
  if (!Array.isArray(body)) return []
  return body.map(toPlace).filter(Boolean)
}

/** Search places by name, Jaipur first. `signal` aborts a query the user has typed past. */
export async function searchPlaces(query, { signal } = {}) {
  const q = query.trim()
  if (q.length < MIN_QUERY) return []
  const local = await runSearch(q, true, signal)
  if (local.length > 0) return local
  // Nothing in or around Jaipur matched. Widening costs a second request, but only on a
  // query that would otherwise show "no results" -- the common case stays one request.
  return runSearch(q, false, signal)
}

/** Name for a point the user dropped by hand. Best-effort: the caller shows coordinates
 *  if this fails, so a reverse-lookup outage costs a label and never a submission. */
export async function describePoint(lat, lon, { signal } = {}) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    format: 'jsonv2',
    zoom: '18',
    'accept-language': 'en',
  })
  const res = await fetch(`${BASE}/reverse?${params}`, { signal })
  if (!res.ok) throw new Error(`reverse -> ${res.status}`)
  const body = await res.json()
  if (!body || !body.display_name) return null
  return splitLabel(body.display_name)
}
