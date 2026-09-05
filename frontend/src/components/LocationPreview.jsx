import { useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import { ImageOverlay, MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import basemap from '../basemap-bounds.json'

// Same threshold and same reasoning as MapView: a couple of tile errors are a flaky
// connection, a dozen is a venue with no wifi.
const TILE_FAILURES_BEFORE_FALLBACK = 4

// Leaflet's default marker pulls its icon from leaflet/dist/images/*.png through CSS, and
// under a bundler those URLs resolve to nothing -- the well-known "marker is invisible in
// production" bug. MapView sidesteps it by only ever drawing CircleMarkers, which cannot be
// dragged. A divIcon is markup we style ourselves, so it needs no image asset, survives the
// build, and can carry the drag handle this needs.
const PIN = L.divIcon({
  className: 'pick-pin',
  html: '<span class="pick-pin-dot"></span><span class="pick-pin-stem"></span>',
  iconSize: [22, 30],
  iconAnchor: [11, 30],
})

// The card this sits in animates in with a transform, so Leaflet measures the container
// mid-animation and caches a wrong size -- the same class of bug MapSync handles on the
// dashboard. Re-measure once the animation has settled, then follow the point.
function Recentre({ at }) {
  const map = useMap()
  useEffect(() => {
    const id = setTimeout(() => {
      map.invalidateSize()
      const size = map.getSize()
      if (size.x === 0 || size.y === 0) return
      map.panTo(at, { animate: true, duration: 0.4 })
    }, 80)
    return () => clearTimeout(id)
  }, [at[0], at[1], map])
  return null
}

function ClickToMove({ onMove }) {
  useMapEvents({ click: (e) => onMove(e.latlng.lat, e.latlng.lng) })
  return null
}

// Confirm-and-adjust. A search result lands on the centre of a road that may run for a
// kilometre, and the leak is at one end of it; GPS indoors can sit a block off. Neither is
// wrong enough to reject and neither is precise enough to submit blind, so the point is
// shown on a map and stays draggable until the resident says it is right.
export default function LocationPreview({ lat, lon, onMove }) {
  const [tileFailures, setTileFailures] = useState(0)
  const offline = tileFailures >= TILE_FAILURES_BEFORE_FALLBACK
  const at = useMemo(() => [lat, lon], [lat, lon])

  return (
    <div className="loc-preview">
      <MapContainer
        className="loc-preview-map"
        center={at}
        zoom={16}
        zoomControl={false}
        scrollWheelZoom={false}
      >
        {/* Attribution stays on. It is an ODbL requirement for the tiles, and it covers the
            search results too -- Nominatim geocodes the same OpenStreetMap data. */}
        {offline ? (
          <ImageOverlay
            url="/basemap.jpg"
            bounds={basemap.bounds}
            pane="tilePane"
            attribution={basemap.attribution}
          />
        ) : (
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            eventHandlers={{ tileerror: () => setTileFailures((n) => n + 1) }}
          />
        )}
        <Marker
          position={at}
          icon={PIN}
          draggable
          eventHandlers={{
            dragend: (e) => {
              const { lat: dLat, lng: dLon } = e.target.getLatLng()
              onMove(dLat, dLon)
            },
          }}
        />
        <ClickToMove onMove={onMove} />
        <Recentre at={at} />
      </MapContainer>
      <p className="loc-preview-hint">
        Drag the pin or tap the map to move it to the exact spot.
      </p>
    </div>
  )
}
