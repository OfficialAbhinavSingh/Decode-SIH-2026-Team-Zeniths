import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  getCityRollup,
  getNationalSummary,
  getStateBoundaries,
  getStateRollup,
} from '../api.js'
import NationalMap, { priorityColor } from '../components/NationalMap.jsx'
import ImpactLedger from '../components/ImpactLedger.jsx'

// National coverage -- an opt-in extra at /national, deliberately NOT the homepage.
// "/" is, and must stay, the working single-city dashboard: that is the thing actually
// judged, and it must never depend on the national data pipelines having been run
// against whatever database is live. City zoom -- the single-city MVP view, now
// reusable for any city -- lives at /city/:cityCode. Reuses the same .app/.workspace/
// .topbar/.list-pane/.map-pane shell Dashboard.jsx defines, so this reads as the same
// product zoomed out rather than a bolted-on second app.
export default function National() {
  const [summary, setSummary] = useState(null)
  const [states, setStates] = useState(null)
  const [stateStats, setStateStats] = useState([])
  const [cities, setCities] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedState, setSelectedState] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([getNationalSummary(), getStateBoundaries(), getStateRollup(), getCityRollup()])
      .then(([s, geo, stateRows, cityRows]) => {
        setSummary(s)
        setStates(geo)
        setStateStats(stateRows)
        setCities(cityRows)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const rankedStates = useMemo(
    () => [...stateStats].sort((a, b) => b.max_priority - a.max_priority),
    [stateStats],
  )

  const visibleCities = useMemo(
    () => (selectedState ? cities.filter((c) => c.state === selectedState) : cities),
    [cities, selectedState],
  )

  const topCities = useMemo(
    () => [...cities].sort((a, b) => b.max_priority - a.max_priority).slice(0, 12),
    [cities],
  )

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <img className="brand-mark" src="/logo.png" alt="" width="30" height="30" />
          <span className="brand-name">NeerDrishti</span>
        </Link>
        <span className="topbar-city">Pan-India water leak intelligence (opt-in extra)</span>
        <span className="topbar-spacer" />
        <Link to="/report" className="cta">
          Report a leak
        </Link>
      </header>

      <div className="workspace">
        <section className="list-pane" aria-label="National coverage">
          <div className="list-head">National coverage</div>
          <div className="list-scroll national-scroll">
            {error && (
              <p className="empty error">
                Could not reach the API ({error}).
                <br />
                Is the backend running?
              </p>
            )}
            {loading && !error && <p className="empty">Loading national data…</p>}

            <ImpactLedger summary={summary} />

            <h2 className="rail-head">Worst states</h2>
            <div className="state-list">
              {rankedStates.slice(0, 12).map((s) => (
                <div
                  key={s.state}
                  className={`state-row${s.state === selectedState ? ' selected' : ''}`}
                  onClick={() => setSelectedState(s.state === selectedState ? null : s.state)}
                >
                  <span className="swatch" style={{ background: priorityColor(s.max_priority) }} />
                  <span className="state-name">{s.state}</span>
                  <span className="state-score">{s.max_priority.toFixed(0)}</span>
                </div>
              ))}
            </div>

            <h2 className="rail-head">Cities to inspect first</h2>
            <div className="state-list">
              {topCities.map((c) => (
                <div
                  key={c.city_code}
                  className="state-row"
                  onClick={() => navigate(`/city/${c.city_code}`)}
                >
                  <span className="swatch" style={{ background: priorityColor(c.max_priority) }} />
                  <span className="state-name">
                    {c.city}, {c.state}
                  </span>
                  <span className="state-score">{c.max_priority.toFixed(0)}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="map-pane" aria-label="National map">
          <NationalMap
            states={states}
            stateStats={stateStats}
            cities={visibleCities}
            onSelectCity={(c) => navigate(`/city/${c.city_code}`)}
          />
        </section>
      </div>
    </div>
  )
}
