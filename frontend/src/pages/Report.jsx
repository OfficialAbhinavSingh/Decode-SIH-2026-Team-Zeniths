import { useState } from 'react'
import { Link } from 'react-router-dom'
import { submitReport } from '../api.js'

// Web fallback for the WhatsApp intake (R5). WhatsApp Business API approval can be slow,
// so this form must exist -- the demo can never depend on Meta approving us in time.
export default function Report() {
  const [description, setDescription] = useState('')
  const [coords, setCoords] = useState(null)
  const [status, setStatus] = useState(null)

  const useMyLocation = () => {
    navigator.geolocation?.getCurrentPosition(
      (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setStatus('Could not read your location — type coordinates instead.'),
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setStatus('Sending…')
    try {
      const res = await submitReport({ channel: 'web', description, ...coords })
      setStatus(
        res.zone_id
          ? `Thanks — logged against zone ${res.zone_id}.`
          : 'Thanks — logged, but the location fell outside our mapped zones.',
      )
      setDescription('')
    } catch (err) {
      setStatus(err.message)
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
      {coords ? (
        <p className="empty">
          Pinned at {coords.lat.toFixed(5)}, {coords.lon.toFixed(5)}
        </p>
      ) : (
        <p className="empty">We need a location to match your report to a zone.</p>
      )}

      <div className="actions">
        <button type="button" className="secondary" onClick={useMyLocation}>
          {coords ? 'Update location' : 'Use my location'}
        </button>
        <button type="submit" disabled={!coords}>Send report</button>
      </div>
      {status && <p className="empty">{status}</p>}
    </form>
  )
}
