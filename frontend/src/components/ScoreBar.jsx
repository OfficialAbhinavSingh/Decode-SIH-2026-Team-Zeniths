// One signal's contribution, drawn as a bar. Null means the signal is absent for this
// zone -- which is not the same as scoring zero, and the UI must say so.
export default function ScoreBar({ label, value, color }) {
  const missing = value === null || value === undefined
  return (
    <div className="bar-row">
      <div className="label">
        <span>{label}</span>
        <span>{missing ? 'no data' : value.toFixed(1)}</span>
      </div>
      <div className="bar">
        <span style={{ width: `${missing ? 0 : value}%`, background: color }} />
      </div>
    </div>
  )
}
