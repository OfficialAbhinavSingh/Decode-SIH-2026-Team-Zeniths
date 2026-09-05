import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import Dashboard from './pages/Dashboard.jsx'
import Report from './pages/Report.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
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
