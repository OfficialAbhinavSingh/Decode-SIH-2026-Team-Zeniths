import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getScores, getScoresGeojson, getZone } from '../api.js'
import MapView, { scoreColor } from '../components/MapView.jsx'
import ZoneDetail from '../components/ZoneDetail.jsx'
import Legend from '../components/Legend.jsx'

const DEFAULT_CENTER = [26.9124, 75.7873] // Jaipur; overridden by the first zone loaded

// ROLES.md R4 deliverable #2 is "Top 10 zones to inspect" -- that is the list a repair
// crew would actually be handed. The rest stay one click away rather than being cut.
const TOP_N = 10

const MOBILE_BREAKPOINT = 820

function timeAgo(iso) {
  if (!iso) return null
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (Number.isNaN(seconds)) return null
  if (seconds < 90) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

// window.innerWidth read directly during render doesn't update on resize/rotation --
// React only re-renders on a state change, and a resize alone isn't one. Tracking it in
// state means the mobile sidebar-hides-behind-the-detail-panel behaviour reacts live.
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.innerWidth <= MOBILE_BREAKPOINT,
  )
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return isMobile
}

export default function Dashboard() {
  const [scores, setScores] = useState([])
  const [geojson, setGeojson] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const isMobile = useIsMobile()

  useEffect(() => {
    Promise.all([getScores(null, 500), getScoresGeojson()])
      .then(([s, g]) => {
        setScores(s)
        setGeojson(g)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedId) return setFlyTarget(null)
    getZone(selectedId).then(setFlyTarget).catch(() => setFlyTarget(null))
  }, [selectedId])

  const selected = useMemo(
    () => scores.find((s) => s.zone_id === selectedId) || null,
    [scores, selectedId],
  )

  const visible = showAll ? scores : scores.slice(0, TOP_N)
  const freshness = timeAgo(scores[0]?.computed_at)

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
            {freshness && (
              <span className="navbar-link" title="When the fusion engine last recomputed">
                Scored {freshness}
              </span>
            )}
            <Link to="/report" className="navbar-cta">Report a Leak →</Link>
          </nav>
        </header>

        <aside
          className="sidebar"
          style={{ display: selectedId && isMobile ? 'none' : 'flex', flexDirection: 'column' }}
        >
          <h2>
            {showAll
              ? `All ${scores.length} zones`
              : `Top ${Math.min(TOP_N, scores.length) || ''} to inspect`}
          </h2>

          {loading && (
            <>
              <p className="empty">Loading zone scores…</p>
              {[0, 1, 2, 3].map((i) => (
                <div className="skeleton" key={i} />
              ))}
            </>
          )}

          {error && (
            <p className="empty">
              Could not reach the API ({error}).
              <br />
              Is the backend running on :8000?
            </p>
          )}

          {!loading && !error && scores.length === 0 && (
            <p className="empty">
              No scores yet. Run <code>python seed.py</code> in <code>backend/</code>, then reload.
            </p>
          )}

          {visible.map((s) => (
            <div
              key={s.zone_id}
              className={`zone-card${s.zone_id === selectedId ? ' selected' : ''}`}
              onClick={() => setSelectedId(s.zone_id)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setSelectedId(s.zone_id)}
              role="button"
              tabIndex={0}
            >
              <div className="row">
                <span className="name">
                  #{s.rank} {s.name}
                </span>
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

          {!loading && scores.length > TOP_N && (
            <button className="link-button" onClick={() => setShowAll((v) => !v)}>
              {showAll ? `Show top ${TOP_N} only` : `Show all ${scores.length} zones`}
            </button>
          )}

          {!loading && !error && scores.length > 0 && (
            <p className="disclosure">
              Billing figures are <strong>synthetic</strong>, modelled on published CPHEEO /
              AMRUT / Jal Jeevan Mission non-revenue-water benchmarks. Satellite NDVI and citizen
              reports are real. See <code>docs/SCOPE.md</code>.
            </p>
          )}
        </aside>

        {!loading && scores.length > 0 && <Legend />}
        <ZoneDetail score={selected} onClose={() => setSelectedId(null)} />
      </div>
    </div>
  )
}
