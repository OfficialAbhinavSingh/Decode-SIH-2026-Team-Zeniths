import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
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
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
