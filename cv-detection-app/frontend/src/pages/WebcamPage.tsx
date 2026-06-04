import React from 'react'
import WebcamStream from '../components/WebcamStream'
import StatusHUD from '../components/StatusHUD'

export default function WebcamPage() {
  return (
    <div>
      <div className="mb-4">
        <StatusHUD />
      </div>
      <WebcamStream />
    </div>
  )
}
