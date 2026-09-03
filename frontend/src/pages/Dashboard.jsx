import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getReports, getScores, getScoresGeojson, getZone } from '../api.js'
import MapView from '../components/MapView.jsx'
import ZoneDetail from '../components/ZoneDetail.jsx'
import Legend from '../components/Legend.jsx'
import { FILTERS, firstVertexLatLon, matchesQuery, scoreColor } from '../lib/zones.js'

const DEFAULT_CENTER = [26.9124, 75.7873] // Jaipur; overridden by the first zone loaded

// ROLES.md R4 deliverable #2 is "Top 10 zones to inspect" -- that is the list a repair
// crew would actually be handed. The rest stay one click away rather than being cut.
// A search or a filter is already a deliberate narrowing, so it shows every match.
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

// What actually became of one citizen report, in the report's own terms. A report whose
// GPS fell outside every mapped polygon is stored with zone_id = null (match_zone() in
// backend/app/routers/reports.py) and fusion.py never joins it to a zone -- it is on
// record and it has a ticket, but it is not evidence and it moved no score. The console
// has to say which of those it is, or it repeats the overclaim the Telegram receipt used
// to make.
function reportVerdict(report) {
  if (report.status === 'duplicate') return { label: 'Duplicate', tone: 'idle' }
  if (report.status === 'dismissed') return { label: 'Not a leak report', tone: 'idle' }
  if (!report.zone_id) return { label: 'Outside coverage', tone: 'warn' }
  return { label: `Scoring ${report.zone_id}`, tone: 'ok' }
}

// window.innerWidth read directly during render doesn't update on resize/rotation --
// React only re-renders on a state change, and a resize alone isn't one.
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

function Chevron() {
  return (
    <svg className="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="m9 6 6 6-6 6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function Dashboard() {
  const [scores, setScores] = useState([])
  const [geojson, setGeojson] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('all')
  const [mobileView, setMobileView] = useState('list')
  const [reports, setReports] = useState(null)
  const [intakeOpen, setIntakeOpen] = useState(false)
  const [intakeBusy, setIntakeBusy] = useState(false)
  const isMobile = useIsMobile()
  const rowRefs = useRef({})

  useEffect(() => {
    Promise.all([getScores(null, 500), getScoresGeojson()])
      .then(([s, g]) => {
        setScores(s)
        setGeojson(g)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Loaded on its own, never folded into the Promise.all above. That call's rejection
  // path sets the page-wide error state, so putting the intake strip in it would let a
  // failing /api/reports blank out the ranked list and the map. Here a failure only
  // leaves `reports` null, which hides the strip and nothing else.
  const loadReports = useCallback(() => {
    setIntakeBusy(true)
    getReports(8)
      .then(setReports)
      .catch(() => setReports(null))
      .finally(() => setIntakeBusy(false))
  }, [])

  useEffect(() => {
    loadReports()
  }, [loadReports])

  useEffect(() => {
    if (!selectedId) return setFlyTarget(null)
    getZone(selectedId).then(setFlyTarget).catch(() => setFlyTarget(null))
  }, [selectedId])

  // ScoreOut carries no ward, but the GeoJSON properties do -- so the search box can
  // match "Ward 3" the way the placeholder promises.
  const meta = useMemo(() => {
    const byId = {}
    for (const f of geojson?.features || []) byId[f.properties.zone_id] = f.properties
    return byId
  }, [geojson])

  const city = geojson?.features?.[0]?.properties?.city || null

  const matches = useMemo(
    () =>
      scores.filter(
        (s) => FILTERS[filter].test(s) && matchesQuery(s, meta[s.zone_id]?.ward, query),
      ),
    [scores, filter, query, meta],
  )

  const narrowed = filter !== 'all' || query.trim() !== ''
  const visible = narrowed || showAll ? matches : matches.slice(0, TOP_N)
  const matchIds = useMemo(
    () => (narrowed ? new Set(matches.map((s) => s.zone_id)) : null),
    [narrowed, matches],
  )

  // A zone the current search or filter excludes must not stay selected: its row is gone
  // from the list, so the open evidence panel would simply vanish while the map kept the
  // zone highlighted and un-closable.
  useEffect(() => {
    if (selectedId && !matches.some((s) => s.zone_id === selectedId)) setSelectedId(null)
  }, [matches, selectedId])

  const freshness = timeAgo(scores[0]?.computed_at)
  const center = firstVertexLatLon(geojson?.features?.[0]?.geometry) || DEFAULT_CENTER

  const select = (zoneId) => {
    const next = zoneId === selectedId ? null : zoneId
    setSelectedId(next)
    // Clicking a polygon on the map should move the list to that zone, not leave the
    // crew hunting for it -- and if the zone is outside the current Top 10, show all.
    if (next && !visible.some((s) => s.zone_id === next)) setShowAll(true)
    if (next) {
      requestAnimationFrame(() =>
        rowRefs.current[next]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }),
      )
    }
  }

  const headline = loading
    ? 'Loading zone scores'
    : narrowed
      ? FILTERS[filter].describe(matches.length, city) +
        (query.trim() ? ` matching “${query.trim()}”` : '')
      : showAll
        ? `All ${scores.length} zones${city ? ` in ${city}` : ''}, ranked`
        : `Top ${Math.min(TOP_N, scores.length) || ''} to inspect${city ? ` in ${city}` : ''}`

  const listHidden = isMobile && mobileView !== 'list'
  const mapHidden = isMobile && mobileView !== 'map'

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <img className="brand-mark" src="/logo.png" alt="" width="30" height="30" />
          <span className="brand-name">NeerDrishti</span>
        </Link>

        <div className="search">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a zone or ward…"
            aria-label="Search zones by name or ward"
          />
          {query && (
            <button className="search-clear" onClick={() => setQuery('')} aria-label="Clear search">
              ×
            </button>
          )}
        </div>

        <div className="filters" role="group" aria-label="Filter zones">
          {Object.entries(FILTERS).map(([key, f]) => (
            <button
              key={key}
              className="pill"
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {f.label}
            </button>
          ))}
        </div>

        <span className="topbar-spacer" />

        {freshness && (
          <span className="freshness" title="When the fusion engine last recomputed">
            <span className="dot" />
            <span className="said">Scored&nbsp;</span>
            {freshness}
          </span>
        )}

        <Link to="/report" className="cta">
          Report a leak
        </Link>
      </header>

      <div className="workspace">
        <section className="list-pane" data-hidden={listHidden} aria-label="Ranked zones">
          <div className="list-head">{headline}</div>

          <div className="list-scroll">
            {loading && [0, 1, 2, 3, 4, 5].map((i) => <div className="skeleton" key={i} />)}

            {error && (
              <p className="empty error">
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

            {!loading && !error && scores.length > 0 && matches.length === 0 && (
              <p className="empty">
                No zone matches this filter.{' '}
                <button
                  className="ghost-btn"
                  onClick={() => {
                    setFilter('all')
                    setQuery('')
                  }}
                >
                  Clear
                </button>
              </p>
            )}

            {visible.map((s) => {
              const open = s.zone_id === selectedId
              return (
                <div
                  key={s.zone_id}
                  className={`zone${open ? ' selected' : ''}`}
                  ref={(el) => {
                    rowRefs.current[s.zone_id] = el
                  }}
                >
                  <button
                    className="zone-head"
                    onClick={() => select(s.zone_id)}
                    aria-expanded={open}
                  >
                    <span
                      className="zone-dot"
                      style={{ background: scoreColor(s.fusion_score) }}
                      aria-hidden="true"
                    />
                    <span className="zone-text">
                      <span className="zone-name">{s.name}</span>
                      <span className="zone-sub">
                        Rank #{s.rank} · <span className="cap">{s.confidence}</span> confidence ·{' '}
                        {s.signals_used}/3 signals
                      </span>
                    </span>
                    <span className="zone-score" style={{ color: scoreColor(s.fusion_score) }}>
                      {s.fusion_score.toFixed(0)}
                    </span>
                    <Chevron />
                  </button>

                  {open && (
                    <ZoneDetail
                      score={s}
                      onShowOnMap={isMobile ? () => setMobileView('map') : null}
                    />
                  )}
                </div>
              )
            })}

            {!loading && !narrowed && scores.length > TOP_N && (
              <p className="empty">
                <button className="ghost-btn" onClick={() => setShowAll((v) => !v)}>
                  {showAll ? `Show top ${TOP_N} only` : `Show all ${scores.length} zones`}
                </button>
              </p>
            )}
          </div>

          {reports && reports.length > 0 && (
            <div className="intake" data-open={intakeOpen}>
              <button
                className="intake-bar"
                onClick={() => setIntakeOpen((v) => !v)}
                aria-expanded={intakeOpen}
              >
                <span className="intake-title">Citizen intake</span>
                <span className="intake-count">{reports.length} most recent</span>
                <Chevron />
              </button>

              {intakeOpen && (
                <div className="intake-body">
                  <div className="intake-list">
                    {reports.map((r) => {
                      const verdict = reportVerdict(r)
                      const when = timeAgo(r.reported_at)
                      return (
                        <div className="intake-row" key={r.id}>
                          <span className={`intake-tag t-${verdict.tone}`}>{verdict.label}</span>
                          <span className="intake-desc">
                            {r.description || 'No description sent'}
                          </span>
                          <span className="intake-meta">
                            #{r.id} · {r.channel}
                            {when ? ` · ${when}` : ''}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                  <div className="intake-foot">
                    <button className="ghost-btn" onClick={loadReports} disabled={intakeBusy}>
                      {intakeBusy ? 'Refreshing…' : 'Refresh'}
                    </button>
                    <span className="intake-note">
                      Reports outside the mapped zones are recorded and ticketed, never scored.
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {!loading && !error && scores.length > 0 && (
            <p className="disclosure">
              Billing figures are <strong>synthetic</strong>, modelled on published CPHEEO / AMRUT /
              Jal Jeevan Mission non-revenue-water benchmarks. Satellite NDVI and citizen reports
              are real. See <code>docs/SCOPE.md</code>.
            </p>
          )}
        </section>

        <section className="map-pane" data-hidden={mapHidden} aria-label="Zone map">
          <MapView
            geojson={geojson}
            selectedId={selectedId}
            onSelect={select}
            center={center}
            flyTarget={flyTarget}
            matchIds={matchIds}
            resizeToken={mapHidden ? 'hidden' : `${mobileView}-${isMobile}`}
          />
          {!loading && scores.length > 0 && <Legend />}
        </section>
      </div>

      {isMobile && (
        <div className="view-switch" role="group" aria-label="Switch view">
          <button aria-pressed={mobileView === 'list'} onClick={() => setMobileView('list')}>
            List
          </button>
          <button aria-pressed={mobileView === 'map'} onClick={() => setMobileView('map')}>
            Map
          </button>
        </div>
      )}
    </div>
  )
}
