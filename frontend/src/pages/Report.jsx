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
  const [status, setStatus] = useState(null)
  const [sending, setSending] = useState(false)

  // Browser geolocation fails often in practice -- denied permission, no HTTPS, a desktop
  // with no GPS, a venue with no signal. Typing coordinates has to be a real path, not a
  // suggestion in an error string, or the fallback form has its own fallback missing.
  const manualLat = Number.parseFloat(manual.lat)
  const manualLon = Number.parseFloat(manual.lon)
  const manualValid = inRange(manualLat, 90) && inRange(manualLon, 180)
  const effective = coords || (manualValid ? { lat: manualLat, lon: manualLon } : null)

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatus('This browser has no location support — type the coordinates below instead.')
      return
    }
    setStatus('Finding your location…')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        setStatus(null)
      },
      () => setStatus('Could not read your location — type the coordinates below instead.'),
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!effective) return
    setSending(true)
    setStatus('Sending…')
    try {
      const res = await submitReport({ channel: 'web', description, ...effective })
      setStatus(
        res.zone_id
          ? `Thanks — logged against zone ${res.zone_id}.`
          : 'Thanks — logged, but the location fell outside our mapped zones.',
      )
      setDescription('')
    } catch (err) {
      setStatus(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="form" onSubmit={submit}>
      <Link to="/" className="tag">← Dashboard</Link>
      <h1 style={{ fontSize: 20 }}>Report a water leak</h1>
      <p className="empty">
        Seeing water on the road, or low pressure for days? Tell us where.
      </p>

      <label htmlFor="desc">What do you see?</label>
      <textarea
        id="desc"
        rows={4}
        required
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Water flowing on the road near the school gate since Monday"
      />

      <label>Location</label>
      {effective ? (
        <p className="empty">
          Pinned at {effective.lat.toFixed(5)}, {effective.lon.toFixed(5)}
          {coords ? ' (from your device)' : ' (typed)'}
        </p>
      ) : (
        <p className="empty">We need a location to match your report to a zone.</p>
      )}

      <div className="actions">
        <button type="button" className="secondary" onClick={useMyLocation}>
          {coords ? 'Update location' : 'Use my location'}
        </button>
      </div>

      <details className="manual" open={!coords && !!status}>
        <summary>Or type coordinates</summary>
        <div className="coord-grid">
          <div>
            <label htmlFor="lat">Latitude</label>
            <input
              id="lat"
              inputMode="decimal"
              placeholder="26.91240"
              value={manual.lat}
              onChange={(e) => {
                setManual((m) => ({ ...m, lat: e.target.value }))
                setCoords(null)
              }}
            />
          </div>
          <div>
            <label htmlFor="lon">Longitude</label>
            <input
              id="lon"
              inputMode="decimal"
              placeholder="75.78730"
              value={manual.lon}
              onChange={(e) => {
                setManual((m) => ({ ...m, lon: e.target.value }))
                setCoords(null)
              }}
            />
          </div>
        </div>
        {manual.lat && manual.lon && !manualValid && (
          <p className="empty warn">
            Latitude must be between -90 and 90, longitude between -180 and 180.
          </p>
        )}
      </details>

      <div className="actions">
        <button type="submit" disabled={!effective || sending}>
          {sending ? 'Sending…' : 'Send report'}
        </button>
      </div>
      {status && <p className="empty">{status}</p>}
    </form>
  )
}
