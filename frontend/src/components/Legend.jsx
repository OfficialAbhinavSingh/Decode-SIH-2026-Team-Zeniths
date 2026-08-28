import { INSPECT_FIRST_MIN, scoreColor } from '../lib/zones.js'

// A judge looking at a coloured map has about three seconds to work out what red means.
// The colours come from scoreColor() rather than being repeated here, so the legend can
// never drift out of step with the map it explains.
const BUCKETS = [
  { from: INSPECT_FIRST_MIN, label: 'Inspect first' },
  { from: 60, label: 'High' },
  { from: 40, label: 'Watch' },
  { from: 20, label: 'Low' },
  { from: 0, label: 'Normal' },
]

export default function Legend() {
  return (
    <div className="legend">
      <div className="legend-title">Priority score</div>
      {BUCKETS.map((b) => (
        <div className="legend-row" key={b.from}>
          <span className="legend-swatch" style={{ background: scoreColor(b.from) }} />
          <span className="legend-label">{b.label}</span>
          <span className="legend-range">{b.from}+</span>
        </div>
      ))}
      <div className="legend-foot">Ranked within the city, not an absolute scale.</div>
    </div>
  )
}
