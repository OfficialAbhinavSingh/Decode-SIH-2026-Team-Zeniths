import { useEffect } from 'react'
import { CircleMarker, GeoJSON, MapContainer, TileLayer, useMap } from 'react-leaflet'
import { centroidOf, scoreColor } from '../lib/zones.js'

// Leaflet measures its container once and caches the result. Two things follow from that,
// and they have to be handled together:
//
//   1. A pane revealed by the mobile view switch was display:none when the map mounted, so
//      it renders as a grey box with the tiles stuck in the corner until invalidateSize().
//   2. flyTo() on a 0x0 container projects to (NaN, NaN) and *throws* -- which tears the
//      whole map out of the tree. Selecting a zone from the mobile list, where the map pane
//      is hidden, hit this every time.
//
// So: re-measure first, then only fly if the pane is actually on screen. A selection made
// while the map was hidden flies as soon as the switch reveals it, because showToken
// changes and this effect runs again.
function MapSync({ zone, showToken }) {
  const map = useMap()
  useEffect(() => {
    const id = setTimeout(() => {
      map.invalidateSize()
      const size = map.getSize()
      if (!zone || size.x === 0 || size.y === 0) return
      const { centroid_lat: lat, centroid_lon: lon } = zone
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return
      map.flyTo([lat, lon], 15, { duration: 0.6 })
    }, 60)
    return () => clearTimeout(id)
  }, [zone, showToken, map])
  return null
}

export default function MapView({ geojson, selectedId, onSelect, center, flyTarget, matchIds, resizeToken }) {
  // A filter narrows which zones get a pin, but every polygon stays on the map. Hiding
  // the rest would hide the city, and "this zone is bad" only means something next to the
  // zones that are not. Non-matching polygons fade instead.
  const filtered = matchIds !== null && matchIds !== undefined

  const style = (feature) => {
    const { zone_id: id, fusion_score: score } = feature.properties
    const isSelected = id === selectedId
    const isMatch = !filtered || matchIds.has(id)
    return {
      color: isSelected ? '#101828' : '#ffffff',
      weight: isSelected ? 2.5 : 0.8,
      fillColor: scoreColor(score),
      fillOpacity: isSelected ? 0.82 : isMatch ? 0.55 : 0.14,
      opacity: isMatch ? 0.9 : 0.25,
    }
  }

  const onEachFeature = (feature, layer) => {
    const p = feature.properties
    layer.bindTooltip(`${p.name} — ${p.fusion_score.toFixed(0)}`, { sticky: true })
    layer.on('click', () => onSelect(p.zone_id))
  }

  const pins = (geojson?.features || [])
    .filter((f) => !filtered || matchIds.has(f.properties.zone_id))
    .map((f) => ({ ...f.properties, at: centroidOf(f.geometry) }))
    .filter((p) => p.at)

  return (
    <MapContainer className="map" center={center} zoom={13} scrollWheelZoom zoomControl={false}>
      {/* Plain OpenStreetMap. A CARTO basemap was tried and rendered as a tiled "API KEY
          REQUIRED" watermark -- their per-tile key requirement is not consistent across
          zoom levels, so it can look fine in a quick check and still break on the exact
          area used at demo time. Swapping basemap needs a real key in an env var first. */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {geojson && (
        // key forces a re-render when the selection or filter changes; Leaflet caches
        // styles otherwise and the fade never applies.
        <GeoJSON
          key={`${selectedId}-${geojson.features.length}-${filtered ? matchIds.size : 'all'}`}
          data={geojson}
          style={style}
          onEachFeature={onEachFeature}
        />
      )}

      {pins.map((p) => (
        <CircleMarker
          key={p.zone_id}
          center={p.at}
          radius={p.zone_id === selectedId ? 9 : 7}
          pathOptions={{
            color: '#ffffff',
            weight: 2.5,
            fillColor: scoreColor(p.fusion_score),
            fillOpacity: 1,
          }}
          eventHandlers={{ click: () => onSelect(p.zone_id) }}
        />
      ))}

      {selectedId &&
        pins
          .filter((p) => p.zone_id === selectedId)
          .map((p) => (
            <CircleMarker
              key={`${p.zone_id}-pulse`}
              center={p.at}
              radius={9}
              interactive={false}
              className="pin-pulse"
              pathOptions={{
                color: scoreColor(p.fusion_score),
                weight: 2,
                fill: false,
              }}
            />
          ))}

      <MapSync zone={flyTarget} showToken={resizeToken} />
    </MapContainer>
  )
}
