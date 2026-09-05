import { GeoJSON, MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import { useEffect, useMemo } from 'react'

const INDIA_CENTER = [22.5, 80.0]

// A continuous scale calibrated to what the national data actually spans (see
// docs/PAN-INDIA-COVERAGE.md): most cities cluster 20-60, so the ramp has real resolution there
// instead of saving its range for a 90+ that only a handful of zones reach.
export function priorityColor(score) {
  if (score >= 75) return '#d9342b'
  if (score >= 55) return '#f0603c'
  if (score >= 35) return '#f0a848'
  if (score >= 15) return '#c9cf4a'
  return '#4aa96c'
}

function FitIndia({ bounds }) {
  const map = useMap()
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [16, 16] })
  }, [bounds, map])
  return null
}

// State choropleth (fill) + a city bubble layer sized by zones scored, coloured by its
// worst zone. Two layers because a state is a policy unit (whose water board do we call)
// and a city is where a crew actually goes -- collapsing them into one layer would force
// picking only one of those two questions to answer.
// Rank -> 0-100 by position in a sorted list. Every city plants at least one seeded
// "hotspot" zone (see pipelines/geo/seed_national.py), so a state's WORST zone is
// almost always severe -- coloring the choropleth by max_priority paints nearly the
// whole country the same shade of red and the map stops being informative. Typical
// condition (mean_priority) has real spread (this run: 28-49), but that range sits in
// one band of a fixed 0-100 scale too. Percentile rank guarantees the choropleth uses
// its full colour range regardless of how compressed the underlying numbers are -- the
// same fix `services/fusion.percentile_rank` applies to a single city's zone map.
function percentileRank(values) {
  if (values.length <= 1) return new Map(values.map((v) => [v, 100]))
  const sorted = [...values].sort((a, b) => a - b)
  const rank = new Map()
  values.forEach((v) => {
    const below = sorted.filter((x) => x < v).length
    rank.set(v, (below / (values.length - 1)) * 100)
  })
  return rank
}

export default function NationalMap({ states, stateStats, cities, onSelectCity }) {
  const byState = useMemo(() => {
    const ranks = percentileRank(stateStats.map((r) => r.mean_priority))
    const map = new Map()
    for (const row of stateStats) map.set(row.state, { ...row, rank: ranks.get(row.mean_priority) })
    return map
  }, [stateStats])

  const style = (feature) => {
    const stat = byState.get(feature.properties.state)
    return {
      color: '#0d1117',
      weight: 0.6,
      fillColor: stat ? priorityColor(stat.rank) : '#30363d',
      fillOpacity: stat ? 0.6 : 0.25,
    }
  }

  const onEachFeature = (feature, layer) => {
    const stat = byState.get(feature.properties.state)
    const label = stat
      ? `${feature.properties.state} — typical zone ${stat.mean_priority.toFixed(0)}, ` +
        `worst zone ${stat.max_priority.toFixed(0)}, ${stat.high_priority_zones} high-priority zone(s)`
      : `${feature.properties.state} — not yet scored`
    layer.bindTooltip(label, { sticky: true })
  }

  return (
    <MapContainer className="map" center={INDIA_CENTER} zoom={5} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {states && <GeoJSON data={states} style={style} onEachFeature={onEachFeature} />}
      {cities.map((c) => (
        <CircleMarker
          key={c.city_code}
          center={[c.lat, c.lon]}
          radius={Math.max(4, Math.min(16, Math.sqrt(c.zones_scored) * 1.6))}
          pathOptions={{
            color: '#0d1117',
            weight: 1,
            fillColor: priorityColor(c.max_priority),
            fillOpacity: 0.85,
          }}
          eventHandlers={{ click: () => onSelectCity(c) }}
        >
          <Tooltip>
            <strong>{c.city}</strong>, {c.state}
            <br />
            worst zone {c.max_priority.toFixed(0)} · {c.zones_scored} zones scored
            <br />
            {c.water_at_risk_kld.toLocaleString()} kL/day at risk
          </Tooltip>
        </CircleMarker>
      ))}
      <FitIndia bounds={[[6.5, 68], [37.5, 97.5]]} />
    </MapContainer>
  )
}
