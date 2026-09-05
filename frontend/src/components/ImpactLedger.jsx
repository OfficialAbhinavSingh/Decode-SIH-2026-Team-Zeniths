// The "wow factor" strip: turns the fusion score into money and households, so a judge
// (or a commissioner) reads a budget line instead of a number out of a hundred.
// Numbers come from backend/app/services/impact.py; the assumptions are shown, not hidden.
export default function ImpactLedger({ summary }) {
  if (!summary) return null

  const inrCrore = summary.annual_value_inr / 1e7
  const items = [
    { label: 'Cities covered', value: summary.cities_scored.toLocaleString() },
    { label: 'States & UTs', value: summary.states_covered },
    { label: 'Zones scored', value: summary.zones_scored.toLocaleString() },
    {
      label: 'Water at risk / day',
      value: `${Math.round(summary.water_at_risk_kld).toLocaleString()} kL`,
    },
    { label: 'Recoverable value / year', value: `₹${inrCrore.toFixed(1)} Cr` },
    { label: 'Households this would serve', value: summary.households_served.toLocaleString() },
    { label: 'High-priority zones', value: summary.high_priority_zones.toLocaleString() },
    {
      label: 'Population covered',
      value: `${(summary.population_covered / 1e6).toFixed(1)} M`,
    },
  ]

  return (
    <div className="ledger">
      {items.map((item) => (
        <div key={item.label} className="ledger-item">
          <div className="ledger-value">{item.value}</div>
          <div className="ledger-label">{item.label}</div>
        </div>
      ))}
    </div>
  )
}
