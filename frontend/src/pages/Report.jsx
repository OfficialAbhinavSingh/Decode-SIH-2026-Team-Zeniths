import { useState } from 'react'
import { Link } from 'react-router-dom'
import { submitReport } from '../api.js'

export default function Report() {
  const [description, setDescription] = useState('')
  const [coords, setCoords] = useState(null)
  const [status, setStatus] = useState(null) // null | 'loading' | 'success' | 'error'
  const [statusMsg, setStatusMsg] = useState('')
  const [locLoading, setLocLoading] = useState(false)

  const useMyLocation = () => {
    setLocLoading(true)
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setLocLoading(false)
      },
      () => {
        setStatusMsg('Could not read your location.')
        setStatus('error')
        setLocLoading(false)
      },
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setStatus('loading')
    setStatusMsg('')
    try {
      const res = await submitReport({ channel: 'web', description, ...coords })
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
      {/* animated water ripple bg */}
      <div className="report-bg">
        <div className="ripple r1" />
        <div className="ripple r2" />
        <div className="ripple r3" />
      </div>

      {/* Back nav */}
      <Link to="/" className="report-back">
        <span>←</span> Back to Dashboard
      </Link>

      <div className="report-center">
        {status === 'success' ? (
          /* ── Success state ── */
          <div className="report-card success-card">
            <div className="success-icon">✓</div>
            <h2>Report Submitted!</h2>
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
              <div className="report-icon-wrap">
                <span style={{ fontSize: 28 }}>💧</span>
              </div>
              <div>
                <h1 className="report-title">Report a Water Leak</h1>
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

                {coords ? (
                  <div className="loc-confirmed">
                    <span className="loc-dot" />
                    <div>
                      <p className="loc-text">Location captured</p>
                      <p className="loc-coords">{coords.lat.toFixed(5)}, {coords.lon.toFixed(5)}</p>
                    </div>
                    <button type="button" className="loc-change" onClick={useMyLocation}>Change</button>
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
              </div>

              {/* Error */}
              {status === 'error' && (
                <div className="report-error">{statusMsg}</div>
              )}

              {/* Submit */}
              <button
                type="submit"
                className="btn-submit"
                disabled={!coords || status === 'loading'}
              >
                {status === 'loading' ? (
                  <><span className="spinner" /> Sending…</>
                ) : (
                  'Send Report →'
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
