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

export default function Legend({ scope = 'the city' }) {
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
      {/* The one sentence that stops the map being read as "43% of this pipe is leaking".
          It has to name the population the percentile was taken over, because that is the
          only thing that changes between the two views: nationally a 100 is the worst zone
          in India, in a city view it is only the worst zone in that city. */}
      <div className="legend-foot">Ranked across {scope}, not an absolute scale.</div>
    </div>
  )
}
