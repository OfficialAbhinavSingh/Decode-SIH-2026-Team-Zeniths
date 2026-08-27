import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getScores, getScoresGeojson, getZone } from '../api.js'
import MapView, { scoreColor } from '../components/MapView.jsx'
import ZoneDetail from '../components/ZoneDetail.jsx'

const DEFAULT_CENTER = [26.9124, 75.7873] // Jaipur; overridden by the first zone loaded

export default function Dashboard() {
  const [scores, setScores] = useState([])
  const [geojson, setGeojson] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getScores(null, 50), getScoresGeojson()])
      .then(([s, g]) => {
        setScores(s)
        setGeojson(g)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selectedId) return setFlyTarget(null)
    getZone(selectedId).then(setFlyTarget).catch(() => setFlyTarget(null))
  }, [selectedId])

  const selected = useMemo(
    () => scores.find((s) => s.zone_id === selectedId) || null,
    [scores, selectedId],
  )

  const center = geojson?.features?.[0]
    ? [...geojson.features[0].geometry.coordinates[0][0]].reverse()
    : DEFAULT_CENTER

  return (
    <div className="app">
      <div className="map-container">
        <MapView
          geojson={geojson}
          selectedId={selectedId}
          onSelect={setSelectedId}
          center={center}
          flyTarget={flyTarget}
        />
      </div>

      <div className="ui-layer">
        <header className="topbar">
          <nav className="navbar-pill">
            <div className="navbar-logo">
              <span className="navbar-logo-icon">💧</span>
            </div>
            <span className="navbar-brand">NeerDrishti AI</span>
            <div className="navbar-divider" />
            {/* <span className="navbar-link active">Dashboard</span> */}
            {/* <span className="navbar-link">Analytics</span> */}
            {/* <span className="navbar-link">Zones</span> */}
            <Link to="/report" className="navbar-cta">Report a Leak →</Link>
          </nav>
        </header>
        <aside className="sidebar" style={{ display: selectedId && window.innerWidth <= 820 ? 'none' : 'flex', flexDirection: 'column' }}>
          <h2>Inspect first</h2>
          {error && <p className="empty">Could not reach the API ({error}).<br />Is the backend running on :8000?</p>}
          {!error && scores.length === 0 && (
            <p className="empty">
              No scores yet. Run <code>python seed.py</code> in <code>backend/</code>, then reload.
            </p>
          )}
          {scores.map((s) => (
            <div
              key={s.zone_id}
              className={`zone-card${s.zone_id === selectedId ? ' selected' : ''}`}
              onClick={() => setSelectedId(s.zone_id)}
            >
              <div className="row">
                <span className="name">#{s.rank} {s.name}</span>
                <span className="score" style={{ color: scoreColor(s.fusion_score) }}>
                  {s.fusion_score.toFixed(0)}
                </span>
              </div>
              <div className="row" style={{ marginTop: 6 }}>
                <span className={`badge ${s.confidence}`}>{s.confidence}</span>
                <span className="badge">{s.signals_used}/3 signals</span>
              </div>
              <div className="why">{s.explanation}</div>
            </div>
          ))}
        </aside>

        <ZoneDetail score={selected} onClose={() => setSelectedId(null)} />
      </div>
    </div>
  )
}
