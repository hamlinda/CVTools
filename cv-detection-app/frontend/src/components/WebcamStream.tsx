import React from 'react'

export default function WebcamStream() {
  return (
    <div>
      <div>
        <img src="/api/stream" alt="webcam-stream" style={{ maxWidth: '100%' }} />
      </div>
      <div className="mt-2">
        <button className="mr-2 px-2 py-1 bg-blue-600 text-white">Start Stream</button>
        <button className="px-2 py-1 bg-gray-600 text-white">Stop Stream</button>
      </div>
    </div>
  )
}
