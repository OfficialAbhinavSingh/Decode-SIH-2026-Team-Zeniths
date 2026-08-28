import { useEffect, useState } from 'react'
import { getZoneSignals } from '../api.js'
import ScoreBar from './ScoreBar.jsx'

// The "why this zone?" evidence. This is the single most important thing in the demo --
// it is what turns a coloured map into an argument. It renders inline underneath the
// selected row rather than as a panel over the map, so the map stays fully visible while
// a crew reads the reasoning.
export default function ZoneDetail({ score, onShowOnMap }) {
  const [signals, setSignals] = useState(null)
  const [signalsFailed, setSignalsFailed] = useState(false)

  useEffect(() => {
    let live = true
    setSignals(null)
    setSignalsFailed(false)
    getZoneSignals(score.zone_id)
      .then((s) => live && setSignals(s))
      .catch(() => live && setSignalsFailed(true))
    return () => {
      live = false
    }
  }, [score.zone_id])

  return (
    <div className="zone-body">
      <ScoreBar label="Satellite (NDVI anomaly)" value={score.satellite_score} color="var(--sat)" />
      <ScoreBar label="Billing (non-revenue water)" value={score.billing_score} color="var(--bill)" />
      <ScoreBar label="Citizen reports" value={score.citizen_score} color="var(--cit)" />

      <p className="zone-why">{score.explanation}</p>

      {onShowOnMap && (
        <div className="zone-actions">
          <button type="button" className="ghost-btn" onClick={onShowOnMap}>
            Show on map
          </button>
        </div>
      )}

      {signalsFailed && (
        <p className="note">Could not load this zone's underlying signal rows.</p>
      )}

      {signals?.citizen?.length > 0 && (
        <>
          <h3 className="subhead">Citizen reports ({signals.citizen.length})</h3>
          <ul className="reports">
            {signals.citizen.slice(0, 6).map((r) => (
              <li key={r.id}>
                <span className="meta">
                  {r.channel} · {new Date(r.reported_at).toLocaleDateString()}
                </span>
                {r.description}
              </li>
            ))}
          </ul>
        </>
      )}

      {signals?.billing?.[0]?.is_synthetic && (
        <p className="note">
          Billing figures are a <strong>synthetic</strong> dataset calibrated to published
          CPHEEO / AMRUT non-revenue-water benchmarks. See <code>docs/SCOPE.md</code>.
        </p>
      )}
    </div>
  )
}
