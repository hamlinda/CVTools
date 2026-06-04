import React from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import ImageAnalysisPage from './pages/ImageAnalysisPage'
import WebcamPage from './pages/WebcamPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="p-4">
        <header className="mb-4">
          <h1 className="text-2xl font-bold">CV Detection App</h1>
          <nav className="mt-2">
            <Link to="/" className="mr-4 text-blue-600">Image</Link>
            <Link to="/webcam" className="text-blue-600">Webcam</Link>
          </nav>
        </header>

        <Routes>
          <Route path="/" element={<ImageAnalysisPage />} />
          <Route path="/webcam" element={<WebcamPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
