// A judge looking at a coloured map has about three seconds to work out what red means.
// The buckets here must stay in step with scoreColor() in MapView.jsx.
const BUCKETS = [
  { from: 80, label: 'Inspect first', color: '#d9342b' },
  { from: 60, label: 'High', color: '#f0603c' },
  { from: 40, label: 'Watch', color: '#f0a848' },
  { from: 20, label: 'Low', color: '#c9cf4a' },
  { from: 0, label: 'Normal', color: '#4aa96c' },
]

export default function Legend() {
  return (
    <div className="legend">
      <div className="legend-title">Priority score</div>
      {BUCKETS.map((b) => (
        <div className="legend-row" key={b.from}>
          <span className="legend-swatch" style={{ background: b.color }} />
          <span className="legend-label">{b.label}</span>
          <span className="legend-range">{b.from}+</span>
        </div>
      ))}
      <div className="legend-foot">Ranked within the city, not an absolute scale.</div>
    </div>
  )
}
