import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import Dashboard from './pages/Dashboard.jsx'
import National from './pages/National.jsx'
import Report from './pages/Report.jsx'

// React Router keeps the same Dashboard instance mounted across /city/JAI -> /city/MUM --
// it is the same route, just a different param -- so every piece of that page's local
// state (selection, search text, map viewport, offline-tile fallback) would otherwise
// carry over into the new city instead of resetting. `key={cityCode}` forces a clean
// remount on every city switch; the alternative (threading a "reset" effect through every
// one of Dashboard's ten-plus state variables) is the more fragile fix, not the simpler
// one.
function CityRoute() {
  const { cityCode } = useParams()
  return <Dashboard key={cityCode} />
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<National />} />
        <Route path="/city/:cityCode" element={<CityRoute />} />
        {/* No :cityCode -- Dashboard falls back to the backend's city_default (Jaipur in
            the MVP env). Kept for the single-city deploy path in render.yaml, where the
            demo fallback has no national data loaded and this is the only useful view. */}
        <Route path="/city" element={<Dashboard />} />
        <Route path="/report" element={<Report />} />
        {/* render.yaml rewrites every path to index.html so the two routes above survive a
            refresh. Without a catch-all that rewrite also hands /anything-else to a router
            with no match, which renders nothing at all -- a mistyped or stale link came back
            as a blank white page rather than a 404. Send it to the dashboard instead. */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
