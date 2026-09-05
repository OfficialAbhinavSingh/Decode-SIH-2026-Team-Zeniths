import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getScoresGeojson, submitReport } from '../api.js'
import LocationSearch from '../components/LocationSearch.jsx'
import LocationPreview from '../components/LocationPreview.jsx'
import { describePoint } from '../lib/geocode.js'
import { zoneAt } from '../lib/zones.js'

// Web fallback for the WhatsApp intake (R5). WhatsApp Business API approval can be slow,
// so this form must exist -- the demo can never depend on Meta approving us in time.
const inRange = (value, limit) => Number.isFinite(value) && Math.abs(value) <= limit

// A report is only evidence if it matched a zone *and* read as a leak. Those are two
// independent checks: match_zone() returns null for a point outside every polygon, and
// classify() marks an off-topic message 'dismissed'. fusion.py joins on zone_id and
// excludes 'dismissed', so a report failing either one moves no score and reaches no ward
// queue. Telling that resident "our AI will factor your report into zone risk scoring"
// is the same overclaim node 7 of automation/n8n/leak-intake.workflow.json was fixed to
// stop making -- and the web form and Telegram must answer this the same way, or the two
// channels drift and only one of them is honest.
function outcomeCopy(res) {
  if (!res.zone_id) {
    return {
      heading: 'Report logged — outside coverage',
      detail:
        `NeerDrishti currently covers Jaipur. Your report is on record as ticket #${res.id}, ` +
        'but it is not queued for ward dispatch and does not change any zone score.',
    }
  }
  if (res.status !== 'new') {
    return {
      heading: 'Message recorded',
      detail:
        `Saved as ticket #${res.id}, but it was not read as a leak report, so it does not ` +
        'affect zone scoring. Send another describing what you can see and we will log it.',
    }
  }
  return {
    heading: 'Report submitted',
    detail:
      `Logged against zone ${res.zone_id} as ticket #${res.id}. Our AI will factor it into ` +
      'zone risk scoring in the next analysis cycle.',
  }
}

// How the point currently on the form was arrived at. Only the wording differs, but the
// wording matters: "captured" claims GPS accuracy, and a pin the resident dragged onto a
// road from a search result has not earned that claim.
const ORIGIN_TEXT = {
  gps: 'Location captured',
  search: 'Location selected',
  pin: 'Pin placed',
}

export default function Report() {
  const [description, setDescription] = useState('')
  const [coords, setCoords] = useState(null)
  const [origin, setOrigin] = useState(null) // 'gps' | 'search' | 'pin' | null (typed)
  const [placeLabel, setPlaceLabel] = useState(null) // { title, detail } from the geocoder
  const [manual, setManual] = useState({ lat: '', lon: '' })
  const [showManual, setShowManual] = useState(false)
  const [status, setStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [outcome, setOutcome] = useState(null) // what the API said about the last submit
  const [statusMsg, setStatusMsg] = useState('')
  const [locLoading, setLocLoading] = useState(false)
  const [zonesGeo, setZonesGeo] = useState(null)

  // Browser geolocation fails often in practice -- denied permission, no HTTPS, a desktop
  // with no GPS, a venue with no signal. Typing coordinates has to be a real path, not a
  // suggestion in an error string, or the fallback form has its own fallback missing.
  const manualLat = Number.parseFloat(manual.lat)
  const manualLon = Number.parseFloat(manual.lon)
  const manualValid = inRange(manualLat, 90) && inRange(manualLon, 180)
  const effective = coords || (manualValid ? { lat: manualLat, lon: manualLon } : null)
  const hasPoint = Boolean(effective)

  // Zone polygons, only once a point exists -- someone who never sets a location never
  // pays for this request. It powers the "which zone is this?" line below the map, which
  // is a preview of what the backend will decide, so every failure here is silent: no
  // polygons means no line, never a blocked or altered submission.
  useEffect(() => {
    if (!hasPoint || zonesGeo) return undefined
    let cancelled = false
    getScoresGeojson()
      .then((geo) => {
        if (!cancelled) setZonesGeo(geo)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [hasPoint, zonesGeo])

  const matchedZone = effective && zonesGeo ? zoneAt(effective.lat, effective.lon, zonesGeo) : null

  // A dragged pin should say where it landed, but a reverse lookup is slower than the drag
  // and the resident may drag again before it answers. The token discards every reply but
  // the newest, so a slow first lookup cannot overwrite the label of a later pin.
  const lookupToken = useRef(0)
  const labelPoint = (lat, lon) => {
    const token = lookupToken.current + 1
    lookupToken.current = token
    describePoint(lat, lon)
      .then((found) => {
        if (lookupToken.current === token) setPlaceLabel(found)
      })
      .catch(() => {
        if (lookupToken.current === token) setPlaceLabel(null)
      })
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatusMsg('This browser has no location support — search for the place or type the coordinates below instead.')
      setStatus('error')
      setShowManual(true)
      return
    }
    setLocLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        lookupToken.current += 1 // cancel any in-flight label from a previous pin
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setOrigin('gps')
        setPlaceLabel(null)
        setLocLoading(false)
        setStatus(null)
      },
      () => {
        setStatusMsg('Could not read your location — search for the place or type the coordinates below instead.')
        setStatus('error')
        setLocLoading(false)
        setShowManual(true)
      },
    )
  }

  const pickPlace = (place) => {
    lookupToken.current += 1 // the search result already carries a name; drop any lookup
    setCoords({ lat: place.lat, lon: place.lon })
    setOrigin('search')
    setPlaceLabel({ title: place.title, detail: place.detail })
    setStatus(null)
  }

  const movePin = (lat, lon) => {
    setCoords({ lat, lon })
    setOrigin('pin')
    setPlaceLabel(null)
    labelPoint(lat, lon)
  }

  const clearLocation = () => {
    lookupToken.current += 1
    setCoords(null)
    setOrigin(null)
    setPlaceLabel(null)
    setManual({ lat: '', lon: '' })
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!effective) return
    setStatus('loading')
    setStatusMsg('')
    try {
      const res = await submitReport({ channel: 'web', description, ...effective })
      setOutcome(outcomeCopy(res))
      setStatus('success')
      setDescription('')
    } catch (err) {
      setStatusMsg(err.message)
      setStatus('error')
    }
  }

  return (
    <div className="report-page">
      <Link to="/" className="report-back">
        <span aria-hidden="true">←</span> Back to dashboard
      </Link>

      <div className="report-center">
        {status === 'success' ? (
          /* ── Success state ── */
          <div className="report-card success-card">
            <div className="success-icon">✓</div>
            <h2>{outcome.heading}</h2>
            <p className="report-sub">{outcome.detail}</p>
            <div className="report-actions" style={{ marginTop: 32 }}>
              <button className="btn-primary" onClick={() => { setOutcome(null); setStatus(null) }}>Submit another</button>
              <Link to="/" className="btn-secondary">View dashboard</Link>
            </div>
          </div>
        ) : (
          /* ── Report form ── */
          <div className="report-card">
            <div className="report-header">
              <img className="report-icon-wrap" src="/logo.png" alt="" width="48" height="48" />
              <div>
                <h1 className="report-title">Report a water leak</h1>
                <p className="report-sub">Help us detect leaks faster. Your report feeds directly into our AI scoring system.</p>
              </div>
            </div>

            <form onSubmit={submit} className="report-form">

              {/* Step 1 – Description */}
              <div className="form-step">
                <div className="step-label">
                  <span className="step-num">1</span>
                  <span>Describe what you see</span>
                </div>
                <textarea
                  id="desc"
                  rows={4}
                  required
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Water flowing on the road near the school gate since Monday morning, no rain in days…"
                  className="report-textarea"
                />
                <p className="field-hint">Be specific — duration, road landmarks, time of day all help.</p>
              </div>

              {/* Step 2 – Location */}
              <div className="form-step">
                <div className="step-label">
                  <span className="step-num">2</span>
                  <span>Set the leak location</span>
                </div>

                {effective ? (
                  <div className="loc-confirmed">
                    <span className="loc-dot" />
                    <div className="loc-body">
                      <p className="loc-text">
                        {placeLabel ? placeLabel.title : ORIGIN_TEXT[origin] || 'Location set'}
                      </p>
                      {placeLabel?.detail && <p className="loc-place">{placeLabel.detail}</p>}
                      <p className="loc-coords">{effective.lat.toFixed(5)}, {effective.lon.toFixed(5)}</p>
                    </div>
                    <button
                      type="button"
                      className="loc-change"
                      onClick={clearLocation}
                    >
                      Change
                    </button>
                  </div>
                ) : (
                  <>
                    {/* Search first: it is the only path that works when you are not at
                        the leak, which is most reports filed from a desk. */}
                    <LocationSearch onPick={pickPlace} disabled={status === 'loading'} />

                    <div className="loc-or"><span>or</span></div>

                    <button
                      type="button"
                      className="btn-location"
                      onClick={useMyLocation}
                      disabled={locLoading}
                    >
                      {locLoading ? (
                        <span className="spinner" />
                      ) : (
                        <span>📍</span>
                      )}
                      {locLoading ? 'Detecting…' : 'Use my current location'}
                    </button>
                  </>
                )}

                {effective ? (
                  <>
                    <LocationPreview lat={effective.lat} lon={effective.lon} onMove={movePin} />
                    {zonesGeo && (
                      matchedZone ? (
                        <p className="field-hint">
                          Falls inside <strong>{matchedZone.name}</strong> — this report will be
                          scored against that zone.
                        </p>
                      ) : (
                        <p className="field-hint warn">
                          This point is outside every monitored zone. The report is still logged,
                          but it will not be scored or queued for a ward.
                        </p>
                      )
                    )}
                  </>
                ) : (
                  <p className="field-hint">
                    Search for the road or landmark nearest the leak, or use your GPS if you are
                    standing at it. We match the point to the nearest monitoring zone.
                  </p>
                )}

                {!coords && (
                  <details
                    className="manual"
                    open={showManual}
                    onToggle={(e) => setShowManual(e.target.open)}
                  >
                    <summary>Or type coordinates</summary>
                    <div className="coord-grid">
                      <div>
                        <label htmlFor="lat">Latitude</label>
                        <input
                          id="lat"
                          inputMode="decimal"
                          placeholder="26.91240"
                          value={manual.lat}
                          onChange={(e) => setManual((m) => ({ ...m, lat: e.target.value }))}
                        />
                      </div>
                      <div>
                        <label htmlFor="lon">Longitude</label>
                        <input
                          id="lon"
                          inputMode="decimal"
                          placeholder="75.78730"
                          value={manual.lon}
                          onChange={(e) => setManual((m) => ({ ...m, lon: e.target.value }))}
                        />
                      </div>
                    </div>
                    {manual.lat && manual.lon && !manualValid && (
                      <p className="field-hint warn">
                        Latitude must be between -90 and 90, longitude between -180 and 180.
                      </p>
                    )}
                  </details>
                )}
              </div>

              {/* Error */}
              {status === 'error' && (
                <div className="report-error">{statusMsg}</div>
              )}

              {/* Submit */}
              <button
                type="submit"
                className="btn-submit"
                disabled={!effective || status === 'loading'}
              >
                {status === 'loading' ? (
                  <><span className="spinner" /> Sending…</>
                ) : (
                  'Send report'
                )}
              </button>

            </form>

            <div className="report-footer">
              <span>🔒 Your location is only used for zone matching and is never stored personally.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
