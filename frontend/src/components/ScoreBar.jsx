// One signal's contribution, drawn as a bar. Null means the signal is absent for this
// zone -- which is not the same as scoring zero, and the UI must say so.
export default function ScoreBar({ label, value, color }) {
  const missing = value === null || value === undefined
  return (
    <div className="bar-row">
      <div className="label">
        <span>{label}</span>
        {missing ? <span className="absent">no data</span> : <b>{value.toFixed(1)}</b>}
      </div>
      <div
        className="bar"
        role="img"
        aria-label={missing ? `${label}: no data` : `${label}: ${value.toFixed(1)} of 100`}
      >
        <span style={{ width: `${missing ? 0 : value}%`, background: color }} />
      </div>
    </div>
  )
}
