import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getCities,
  getNationalGeojson,
  getReports,
  getScores,
  getScoresGeojson,
  getZone,
} from '../api.js'
import CityPicker from '../components/CityPicker.jsx'
import MapView from '../components/MapView.jsx'
import ZoneDetail from '../components/ZoneDetail.jsx'
import Legend from '../components/Legend.jsx'
import { FILTERS, NATIONAL, firstVertexLatLon, matchesQuery, scoreColor } from '../lib/zones.js'

const DEFAULT_CENTER = [26.9124, 75.7873] // Jaipur; overridden by the first zone loaded

// ROLES.md R4 deliverable #2 is "Top 10 zones to inspect" -- that is the list a repair
// crew would actually be handed. The rest stay one click away rather than being cut.
// A search or a filter is already a deliberate narrowing, so it shows every match.
const TOP_N = 10

const MOBILE_BREAKPOINT = 820

// Fallback only. The national view fits the bounds of the cities that are actually loaded,
// which is right whether that is six cities or the whole registry; this is what the map
// opens on for the frame before /api/cities has answered.
const INDIA_CENTER = [22.6, 79.5]
const INDIA_ZOOM = 5

// How many rows the list will put in the DOM at once, however many zones match.
//
// Every other limit here is editorial -- TOP_N is a decision about what a crew should be
// handed. This one is mechanical: "Inspect first" over the whole country matches more than
// a thousand zones, each row carrying a coloured dot and a chevron, and rendering all of
// them stalls the tab for seconds on a click. A city never comes close to it, so nothing
// about the single-city view changes.
const LIST_CAP = 200

// The national FeatureCollection carries the full evidence per zone, so the ranked list is
// derived from it rather than fetched separately. That is what closes the gap a lean map
// payload would leave: at country zoom almost every polygon on screen falls outside any
// top N, and clicking one of those has to open its panel, not nothing.
function scoresFromFeatures(collection) {
  return (collection?.features || [])
    .map((f) => ({ ...f.properties, computed_at: collection.computed_at }))
    .sort((a, b) => a.rank - b.rank)
}

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
  const [cities, setCities] = useState([])
  // Three states, and the third one matters. `undefined` means "we have not been told what
  // is loaded yet" and blocks the data request; NATIONAL means the whole country; null
  // means "whatever CITY_DEFAULT is", sending no ?city= at all, which is how a database
  // holding only the seeded Jaipur grid behaves exactly as it did before any of this.
  //
  // Deciding before fetching costs one round trip on first paint and buys the thing that
  // matters most here: a single-city database never so much as requests the national view,
  // let alone renders a country map over one city's worth of squares.
  const [city, setCity] = useState(undefined)
  const [reports, setReports] = useState(null)
  const [intakeOpen, setIntakeOpen] = useState(false)
  const [intakeBusy, setIntakeBusy] = useState(false)
  const isMobile = useIsMobile()
  const rowRefs = useRef({})

  const national = city === NATIONAL

  useEffect(() => {
    // Still waiting on /api/cities to say whether there is a country to show.
    if (city === undefined) return
    let live = true
    setLoading(true)
    setError(null)
    const load = national
      ? getNationalGeojson().then((g) => [scoresFromFeatures(g), g])
      : Promise.all([getScores(city, 500), getScoresGeojson(city)])
    load
      .then(([s, g]) => {
        // A slow response for the city the user just switched away from must not paint
        // over the one they are actually looking at. Without this guard, picking three
        // cities quickly can leave the list showing whichever request happened to land
        // last rather than the one that is selected.
        if (!live) return
        setScores(s)
        setGeojson(g)
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
    // `national` is derived from `city`, so it cannot change without it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city])

  // Loaded once and kept out of the effect above: a failure here must cost the picker
  // only. `cities` staying empty hides it, and the dashboard falls back to the single
  // default city it has always shown.
  useEffect(() => {
    getCities()
      .then((rows) => {
        setCities(rows)
        // The landing view is the whole country when there is a whole country to land on,
        // and the one seeded city when there is not. Both branches resolve `city` out of
        // `undefined`, which is what releases the data request above -- including the
        // failure branch, or a dead /api/cities would leave the dashboard loading forever.
        setCity(rows.length > 1 ? NATIONAL : null)
      })
      .catch(() => {
        setCities([])
        setCity(null)
      })
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

  // Everything below is scoped to whatever is loaded: a selected zone, a text query, a
  // filter and the expanded list all refer to zones that no longer exist after a switch.
  // Clearing them is what makes the switch feel like arriving somewhere new rather than
  // landing in a filtered, empty list.
  const changeCity = (next) => {
    if (next === city) return
    setCity(next)
    // Drop the old city's data rather than leaving it on screen under the new city's
    // name. The list is already showing skeletons while `loading` is true, and a map that
    // is briefly empty is honest in a way that one still covered in Jaipur's polygons
    // while the header says Pune is not.
    setScores([])
    setGeojson(null)
    setSelectedId(null)
    setFlyTarget(null)
    setQuery('')
    setFilter('all')
    setShowAll(false)
    setMobileView('list')
    // These key off zone id, and no zone id survives a city switch.
    rowRefs.current = {}
  }

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

  // What the loaded data is actually FOR, which is not the same as `city`: when `city` is
  // null no ?city= was sent and only the response says which one the API chose. The
  // headline needs that name, not the null. Nationally the features carry 234 different
  // city names and none of them is the answer.
  const cityLabel = national ? 'India' : geojson?.features?.[0]?.properties?.city || null

  // How to finish the sentence "ranked across ___" wherever a percentile is explained --
  // the legend, and the decode line under a selected zone. Naming the wrong population is
  // the one way these numbers actively mislead: 100 nationally is the worst zone in the
  // country, 100 in a city view is only the worst zone in that city.
  const scope = national ? 'India' : cityLabel || 'the city'

  const matches = useMemo(
    () =>
      scores.filter(
        (s) => FILTERS[filter].test(s) && matchesQuery(s, meta[s.zone_id]?.ward, query),
      ),
    [scores, filter, query, meta],
  )

  const narrowed = filter !== 'all' || query.trim() !== ''
  const shortlist = narrowed || showAll ? matches : matches.slice(0, TOP_N)
  const visible = shortlist.slice(0, LIST_CAP)
  const capped = shortlist.length > visible.length
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

  // A zone clicked on the map has to open its evidence, and neither the Top 10 nor the
  // capped list is guaranteed to contain it -- nationally almost nothing on screen is in
  // either. Rather than expand the list until it does, the selected zone gets a row of its
  // own at the top. Scrolling six thousand rows to find the square you just clicked is not
  // a better answer than putting it where you are already looking.
  const selectedRow =
    selectedId && !visible.some((s) => s.zone_id === selectedId)
      ? matches.find((s) => s.zone_id === selectedId)
      : null
  const rows = selectedRow ? [selectedRow, ...visible] : visible

  const freshness = timeAgo(scores[0]?.computed_at)
  const center = national
    ? INDIA_CENTER
    : firstVertexLatLon(geojson?.features?.[0]?.geometry) || DEFAULT_CENTER

  // Fit what is loaded rather than hardcoding a view of the country: six cities and 234
  // cities want very different framings, and the second one stops being true the moment
  // someone seeds a subset. Built from the city centroids, not from 6,000 polygons.
  const bounds = useMemo(() => {
    if (!national || cities.length < 2) return null
    const lats = cities.map((c) => c.centroid_lat)
    const lons = cities.map((c) => c.centroid_lon)
    return [
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ]
  }, [national, cities])

  const select = (zoneId) => {
    const next = zoneId === selectedId ? null : zoneId
    setSelectedId(next)
    // Clicking a polygon on the map should move the list to that zone, not leave the
    // crew hunting for it -- and if the zone is outside the current Top 10, show all.
    // Not worth doing when the full list is capped anyway: expanding to 200 rows still
    // would not reach a zone ranked 3,000th, and selectedRow has already put it on screen.
    if (next && !visible.some((s) => s.zone_id === next) && matches.length <= LIST_CAP) {
      setShowAll(true)
    }
    if (next) {
      requestAnimationFrame(() =>
        rowRefs.current[next]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }),
      )
    }
  }

  const headline = loading
    ? 'Loading zone scores'
    : narrowed
      ? FILTERS[filter].describe(matches.length, scope) +
        (query.trim() ? ` matching “${query.trim()}”` : '')
      : showAll
        ? `All ${scores.length.toLocaleString()} zones${cityLabel ? ` in ${cityLabel}` : ''}, ranked`
        : `Top ${Math.min(TOP_N, scores.length) || ''} to inspect${cityLabel ? ` in ${cityLabel}` : ''}`

  const listHidden = isMobile && mobileView !== 'list'
  const mapHidden = isMobile && mobileView !== 'map'

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <img className="brand-mark" src="/logo.png" alt="" width="30" height="30" />
          <span className="brand-name">NeerDrishti</span>
        </Link>

        <CityPicker cities={cities} value={city || cityLabel} onChange={changeCity} />

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

            {/* Two audiences, two messages. On a developer's machine the useful thing to say
                is which port nothing is listening on. On the deployed URL a judge sees this
                during a Render cold start, and "is the backend running on :8000?" reads as a
                broken build -- it names a port that does not exist for them and asks them to
                fix our server. */}
            {error && (
              <p className="empty error">
                {import.meta.env.DEV ? (
                  <>
                    Could not reach the API ({error}).
                    <br />
                    Is the backend running on :8000?
                  </>
                ) : (
                  <>
                    Could not load the zone list.
                    <br />
                    The service sleeps when idle — wait a few seconds and reload.
                  </>
                )}
              </p>
            )}

            {!loading && !error && scores.length === 0 && (
              <p className="empty">
                {import.meta.env.DEV ? (
                  <>
                    No scores yet. Run <code>python seed.py</code> in <code>backend/</code>, then reload.
                  </>
                ) : (
                  <>No zones have been scored yet.</>
                )}
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

            {rows.map((s) => {
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
                      cityCount={scores.length}
                      scope={national ? 'across India' : cityLabel ? `in ${cityLabel}` : ''}
                      onShowOnMap={isMobile ? () => setMobileView('map') : null}
                    />
                  )}
                </div>
              )
            })}

            {/* Says so when the list is not showing everything it matched, rather than
                letting a truncated list read as the complete answer. */}
            {capped && (
              <p className="empty">
                Showing the first {LIST_CAP} of {shortlist.length.toLocaleString()} — narrow
                the search or the filter to see the rest.
              </p>
            )}

            {!loading && !narrowed && scores.length > TOP_N && (
              <p className="empty">
                <button className="ghost-btn" onClick={() => setShowAll((v) => !v)}>
                  {showAll
                    ? `Show top ${TOP_N} only`
                    : scores.length > LIST_CAP
                      ? `Show the top ${LIST_CAP} of ${scores.length.toLocaleString()}`
                      : `Show all ${scores.length} zones`}
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

          {/* Every clause in the disclosure below is load-bearing. It sits under the ranked list
              for the whole demo, so a wrong word in it is the most-read untrue thing we could
              ship. It used to say "Satellite NDVI and citizen reports are real", which was false
              for the reports: seed.py writes them with reporter_hash "sha256:seed...", and on
              production today every report actually moving a zone score is a seeded one. The
              intake path being live is a different claim from the stored rows being real, and
              README.md has said so all along -- the dashboard was the copy that drifted. */}
          {!loading && !error && scores.length > 0 && (
            <p className="disclosure">
              {cities.length > 1 ? (
                <>
                  Every signal on this map is <strong>synthetic</strong> — a seeded generator
                  reproducing the Jaipur grid across {cities.length} cities, with billing
                  modelled on published CPHEEO / AMRUT / Jal Jeevan Mission non-revenue-water
                  benchmarks. A real Sentinel-2 export overrides the generated NDVI wherever
                  one has been ingested; everything else here is generated. See{' '}
                  <code>docs/SYNTHETIC-DATA.md</code>.
                </>
              ) : (
                <>
                  Satellite NDVI is <strong>real</strong> Sentinel-2 data. Billing figures are{' '}
                  <strong>synthetic</strong>, modelled on published CPHEEO / AMRUT / Jal Jeevan
                  Mission non-revenue-water benchmarks. The citizen reports in this demo database
                  are <strong>seeded</strong> — the intake path itself is live. See{' '}
                  <code>docs/SCOPE.md</code>.
                </>
              )}
            </p>
          )}
        </section>

        <section className="map-pane" data-hidden={mapHidden} aria-label="Zone map">
          <MapView
            geojson={geojson}
            selectedId={selectedId}
            onSelect={select}
            center={center}
            zoom={national ? INDIA_ZOOM : 13}
            bounds={bounds}
            national={national}
            flyTarget={flyTarget}
            matchIds={matchIds}
            resizeToken={mapHidden ? 'hidden' : `${mobileView}-${isMobile}`}
          />
          {!loading && scores.length > 0 && <Legend scope={scope} />}
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
