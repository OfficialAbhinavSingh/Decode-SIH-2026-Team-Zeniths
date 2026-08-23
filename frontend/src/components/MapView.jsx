import { GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'

// Green (safe) -> red (inspect first). Fusion scores are percentile-ranked within the city
// by the backend, so this ramp always uses its full range instead of collapsing to one hue.
export function scoreColor(score) {
  if (score >= 80) return '#d9342b'
  if (score >= 60) return '#f0603c'
  if (score >= 40) return '#f0a848'
  if (score >= 20) return '#c9cf4a'
  return '#4aa96c'
}

function FlyTo({ zone }) {
  const map = useMap()
  useEffect(() => {
    if (zone) map.flyTo([zone.centroid_lat, zone.centroid_lon], 15, { duration: 0.6 })
  }, [zone, map])
  return null
}

export default function MapView({ geojson, selectedId, onSelect, center, flyTarget }) {
  const style = (feature) => ({
    color: '#0d1117',
    weight: feature.properties.zone_id === selectedId ? 2.5 : 0.8,
    fillColor: scoreColor(feature.properties.fusion_score),
    fillOpacity: feature.properties.zone_id === selectedId ? 0.85 : 0.6,
  })

  const onEachFeature = (feature, layer) => {
    const p = feature.properties
    layer.bindTooltip(`${p.name} — ${p.fusion_score.toFixed(0)}`, { sticky: true })
    layer.on('click', () => onSelect(p.zone_id))
  }

  return (
    <MapContainer className="map" center={center} zoom={13} scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {geojson && (
        // key forces a re-render when scores change; Leaflet caches styles otherwise.
        <GeoJSON
          key={`${selectedId}-${geojson.features.length}`}
          data={geojson}
          style={style}
          onEachFeature={onEachFeature}
        />
      )}
      <FlyTo zone={flyTarget} />
    </MapContainer>
  )
}
