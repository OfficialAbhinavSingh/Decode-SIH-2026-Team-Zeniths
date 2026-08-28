import { useState } from 'react'
import { Link } from 'react-router-dom'
import { submitReport } from '../api.js'

// Web fallback for the WhatsApp intake (R5). WhatsApp Business API approval can be slow,
// so this form must exist -- the demo can never depend on Meta approving us in time.
const inRange = (value, limit) => Number.isFinite(value) && Math.abs(value) <= limit

export default function Report() {
  const [description, setDescription] = useState('')
  const [coords, setCoords] = useState(null)
  const [manual, setManual] = useState({ lat: '', lon: '' })
  const [showManual, setShowManual] = useState(false)
  const [status, setStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [statusMsg, setStatusMsg] = useState('')
  const [locLoading, setLocLoading] = useState(false)

  // Browser geolocation fails often in practice -- denied permission, no HTTPS, a desktop
  // with no GPS, a venue with no signal. Typing coordinates has to be a real path, not a
  // suggestion in an error string, or the fallback form has its own fallback missing.
  const manualLat = Number.parseFloat(manual.lat)
  const manualLon = Number.parseFloat(manual.lon)
  const manualValid = inRange(manualLat, 90) && inRange(manualLon, 180)
  const effective = coords || (manualValid ? { lat: manualLat, lon: manualLon } : null)

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatusMsg('This browser has no location support — type the coordinates below instead.')
      setStatus('error')
      setShowManual(true)
      return
    }
    setLocLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setLocLoading(false)
        setStatus(null)
      },
      () => {
        setStatusMsg('Could not read your location — type the coordinates below instead.')
        setStatus('error')
        setLocLoading(false)
        setShowManual(true)
      },
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!effective) return
    setStatus('loading')
    setStatusMsg('')
    try {
      const res = await submitReport({ channel: 'web', description, ...effective })
      setStatusMsg(
        res.zone_id
          ? `Logged against zone ${res.zone_id}`
          : 'Logged — location fell outside mapped zones.',
      )
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
            <h2>Report submitted</h2>
            <p className="report-sub">{statusMsg}</p>
            <p className="report-sub">Our AI will factor your report into zone risk scoring within the next analysis cycle.</p>
            <div className="report-actions" style={{ marginTop: 32 }}>
              <button className="btn-primary" onClick={() => setStatus(null)}>Submit another</button>
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
                  <span>Pin your location</span>
                </div>

                {effective ? (
                  <div className="loc-confirmed">
                    <span className="loc-dot" />
                    <div>
                      <p className="loc-text">
                        Location {coords ? 'captured' : 'set'}
                      </p>
                      <p className="loc-coords">{effective.lat.toFixed(5)}, {effective.lon.toFixed(5)}</p>
                    </div>
                    <button
                      type="button"
                      className="loc-change"
                      onClick={() => {
                        setCoords(null)
                        setManual({ lat: '', lon: '' })
                      }}
                    >
                      Change
                    </button>
                  </div>
                ) : (
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
                )}
                <p className="field-hint">We match your GPS to the nearest monitoring zone.</p>

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
