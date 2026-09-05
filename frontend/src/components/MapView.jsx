import { useCallback, useEffect, useState } from 'react'
import {
  CircleMarker,
  GeoJSON,
  ImageOverlay,
  MapContainer,
  TileLayer,
  useMap,
} from 'react-leaflet'
import { centroidOf, scoreColor } from '../lib/zones.js'
import basemap from '../basemap-bounds.json'

// How many tile requests have to fail before we accept that there is no network and swap
// to the offline basemap. One or two failures happen on a flaky connection and recover on
// their own; a venue with no wifi produces them by the dozen immediately.
const TILE_FAILURES_BEFORE_FALLBACK = 4

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

// <MapContainer center> and <MapContainer zoom> are read ONCE, when Leaflet constructs the
// map, and never again -- they are not reactive props. Switching city therefore swapped
// every polygon underneath a map still parked over the old city, so the new zones sat
// off-screen and the pane looked empty. This moves the view when the target actually
// changes.
//
// `bounds` wins when it is given, because "show me India" is a question about an extent,
// not about a point: a hardcoded centre and zoom for the country is wrong the moment the
// loaded set of cities is not the whole registry, whereas fitting the bounds of whatever
// was actually loaded is right for one city, for six, or for all of them.
//
// The dependency list is scalars, never the arrays themselves: `center` and `bounds` are
// fresh arrays on every render, so depending on them would re-run this on every keystroke
// in the search box and yank the map back from wherever the user had panned it.
function RecenterOnCity({ center, zoom = 13, bounds, showToken }) {
  const map = useMap()
  const [lat, lon] = center || []
  // The identity of `bounds` changes every render; its contents do not. Depending on the
  // joined string is what keeps this from re-fitting the map continuously.
  const boundsKey = bounds ? bounds.flat().join(',') : null
  useEffect(() => {
    if (boundsKey) {
      // Leaflet measured the mobile map pane at 0x0 while the list was showing, and
      // fitBounds on that computes a nonsense zoom. showToken changes when the view switch
      // reveals the pane, which is what gets the country fitted then rather than never. It
      // is passed as null outside the bounds path, so the single-city view's behaviour on
      // that switch is exactly what it was.
      if (map.getSize().x === 0) return
      map.fitBounds(bounds, { padding: [28, 28] })
      return
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return
    map.setView([lat, lon], zoom)
    // `bounds` is deliberately absent from the deps: boundsKey stands in for its contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lon, zoom, boundsKey, showToken, map])
  return null
}

export default function MapView({
  geojson,
  selectedId,
  onSelect,
  center,
  zoom,
  bounds,
  flyTarget,
  matchIds,
  resizeToken,
  national = false,
}) {
  // The map is the demo. If the venue wifi dies, live OSM tiles never arrive and the map
  // renders as a blank grey box with the zone polygons floating on nothing. This falls back
  // to a pre-built image of the same area (tools/build_offline_basemap.py), georeferenced
  // to real bounds so it pans and zooms correctly underneath the polygons.
  const [tileFailures, setTileFailures] = useState(0)
  const offline = tileFailures >= TILE_FAILURES_BEFORE_FALLBACK
  // A filter narrows which zones get a pin, but every polygon stays on the map. Hiding
  // the rest would hide the city, and "this zone is bad" only means something next to the
  // zones that are not. Non-matching polygons fade instead.
  const filtered = matchIds !== null && matchIds !== undefined

  // useCallback, not a plain arrow, and it matters: react-leaflet's GeoJSON re-applies
  // `style` to every child layer whenever the prop's *identity* changes. A fresh arrow on
  // each render therefore restyles the whole collection on every keystroke -- unnoticeable
  // for one city's 30 squares, six thousand layer updates per character nationally. Pinned
  // to the three things that can actually change a colour.
  const style = useCallback(
    (feature) => {
      const { zone_id: id, fusion_score: score } = feature.properties
      const isSelected = id === selectedId
      const isMatch = !filtered || matchIds.has(id)
      return {
        color: isSelected ? '#101828' : '#ffffff',
        // A 1.3 km square is well under a pixel at the zoom that fits India on screen, so
        // nationally the white hairline is not a border between zones -- it *is* the zone,
        // and 6,000 of them paint the country white. Unselected national polygons are pure
        // fill; a city's grid reads as one blob of its own colour, which is the honest
        // rendering at that scale, and the borders come back the moment you zoom in far
        // enough to have selected something.
        weight: isSelected ? 2.5 : national ? 0 : 0.8,
        stroke: isSelected || !national,
        fillColor: scoreColor(score),
        fillOpacity: isSelected ? 0.82 : isMatch ? (national ? 0.72 : 0.55) : 0.14,
        opacity: isMatch ? 0.9 : 0.25,
      }
    },
    [selectedId, filtered, matchIds, national],
  )

  const onEachFeature = (feature, layer) => {
    const p = feature.properties
    // The city name only earns its place nationally. In a single-city view every tooltip
    // would repeat the name already in the header.
    const where = national && p.city ? `${p.name}, ${p.city}` : p.name
    layer.bindTooltip(`${where} — ${p.fusion_score.toFixed(0)}`, { sticky: true })
    layer.on('click', () => onSelect(p.zone_id))
  }

  // No pins nationally. They exist to make a 1.3 km square findable at city zoom; six
  // thousand of them at country zoom is a solid mat of circles covering the very polygons
  // they are meant to point at, and each one is a separate Leaflet layer to boot. Selecting
  // a zone still flies to it, and at zoom 15 the polygon itself is unmistakable.
  const pins = national
    ? []
    : (geojson?.features || [])
        .filter((f) => !filtered || matchIds.has(f.properties.zone_id))
        .map((f) => ({ ...f.properties, at: centroidOf(f.geometry) }))
        .filter((p) => p.at)

  return (
    <>
    {offline && (
      <div className="offline-badge" role="status">
        Offline basemap — no tile connection
      </div>
    )}
    {/* preferCanvas is read once at construction like center and zoom, so switching scope
        has to rebuild the map -- hence the key. That is the right trade in both directions:
        6,000 SVG paths is a DOM the browser will not pan smoothly, and canvas cannot run
        the CSS keyframes behind .pin-pulse, so the city view keeps SVG and keeps its
        pulsing selection ring. */}
    <MapContainer
      key={national ? 'national' : 'city'}
      className="map"
      center={center}
      zoom={zoom ?? 13}
      preferCanvas={national}
      scrollWheelZoom
      zoomControl={false}
    >
      {/* Plain OpenStreetMap. A CARTO basemap was tried and rendered as a tiled "API KEY
          REQUIRED" watermark -- their per-tile key requirement is not consistent across
          zoom levels, so it can look fine in a quick check and still break on the exact
          area used at demo time. Swapping basemap needs a real key in an env var first. */}
      {offline ? (
        // pane="tilePane" keeps it underneath the polygons and pins, which live in the
        // overlay pane. In the default pane it would cover them.
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

      {geojson && (
        // react-leaflet 4's GeoJSON updates `style` on a prop change but never `data`, so
        // the key is what actually swaps one city's polygons for another's. Dashboard also
        // clears geojson to null across a scope change, which unmounts this outright.
        <GeoJSON
          key={`${national ? 'national' : 'city'}-${geojson.features.length}`}
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

      <RecenterOnCity
        center={center}
        zoom={zoom}
        bounds={bounds}
        showToken={bounds ? resizeToken : null}
      />
      <MapSync zone={flyTarget} showToken={resizeToken} />
    </MapContainer>
    </>
  )
}
