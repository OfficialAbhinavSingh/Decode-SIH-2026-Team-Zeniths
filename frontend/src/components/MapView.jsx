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
  const style = (feature) => {
    const isSelected = feature.properties.zone_id === selectedId;
    return {
      color: isSelected ? '#00f3ff' : 'transparent',
      weight: isSelected ? 3 : 0,
      fillColor: scoreColor(feature.properties.fusion_score),
      fillOpacity: isSelected ? 1 : 0.85,
    };
  }

  const onEachFeature = (feature, layer) => {
    const p = feature.properties
    layer.bindTooltip(`${p.name} — ${p.fusion_score.toFixed(0)}`, { sticky: true })
    layer.on('click', () => onSelect(p.zone_id))
  }

  return (
    <MapContainer className="map" center={center} zoom={13} scrollWheelZoom zoomControl={false}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
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
