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
      {/* The CARTO dark_all tiles this PR shipped with rendered as a tiled "API KEY
          REQUIRED" watermark live -- CARTO's per-tile key requirement isn't consistent
          across zoom/coverage, so it can look fine in a quick check and still break on
          the exact area used at demo time. Plain OSM has no such gate. If a CARTO dark
          basemap is worth the visual upgrade, it needs a real key wired through an env
          var first, verified against the actual demo city/zoom. */}
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
