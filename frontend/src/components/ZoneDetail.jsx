import { useEffect, useState } from 'react'
import { getZoneSignals } from '../api.js'
import ScoreBar from './ScoreBar.jsx'

// The "why this zone?" panel. This is the single most important screen in the demo --
// it is what turns a coloured map into an argument.
export default function ZoneDetail({ score, onClose }) {
  const [signals, setSignals] = useState(null)

  useEffect(() => {
    if (!score) return
    setSignals(null)
    getZoneSignals(score.zone_id).then(setSignals).catch(() => setSignals(null))
  }, [score])

  if (!score) return null

  return (
    <div className="detail">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h3>{score.name}</h3>
      <div className="empty" style={{ marginBottom: 10 }}>
        Rank #{score.rank} · score {score.fusion_score.toFixed(1)} ·{' '}
        <span className={`badge ${score.confidence}`}>{score.confidence} confidence</span>
      </div>

      <ScoreBar label="🛰 Satellite (NDVI anomaly)" value={score.satellite_score} color="var(--sat)" />
      <ScoreBar label="💧 Billing (non-revenue water)" value={score.billing_score} color="var(--bill)" />
      <ScoreBar label="📱 Citizen reports" value={score.citizen_score} color="var(--cit)" />

      <p className="why" style={{ marginTop: 14, lineHeight: 1.5, fontSize: 13 }}>
        {score.explanation}
      </p>

      {signals?.citizen?.length > 0 && (
        <>
          <h2 style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 16, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Citizen reports ({signals.citizen.length})
          </h2>
          <ul className="reports" style={{ margin: 0 }}>
            {signals.citizen.slice(0, 6).map((r) => (
              <li key={r.id}>
                <strong>{r.channel === 'Twitter' ? '🐦' : '📞'} {r.channel}</strong> · {new Date(r.reported_at).toLocaleDateString()}
                <br/>
                <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{r.description}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {signals?.billing?.[0]?.is_synthetic && (
        <p className="empty" style={{ marginTop: 14, fontSize: 11 }}>
          Billing figures are a synthetic dataset calibrated to published CPHEEO/AMRUT
          non-revenue-water benchmarks. See docs/SCOPE.md.
        </p>
      )}
    </div>
  )
}
