import React, { useRef, useState, useCallback } from 'react'

export default function WebcamStream() {
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  const start = useCallback(() => {
    setError(null)
    setStreaming(true)
    // set src on img to begin MJPEG loading
    if (imgRef.current) imgRef.current.src = '/api/stream'
  }, [])

  const stop = useCallback(() => {
    // clear src to stop the browser from fetching the MJPEG stream
    if (imgRef.current) {
      imgRef.current.src = ''
      imgRef.current.removeAttribute('src')
    }
    setStreaming(false)
  }, [])

  const onImgError = useCallback((e: any) => {
    setError('Stream failed to start or was interrupted')
    setStreaming(false)
  }, [])

  return (
    <div>
      <div>
        <img
          ref={imgRef}
          alt="webcam-stream"
          style={{ maxWidth: '100%', background: '#111' }}
          onError={onImgError}
        />
      </div>
      <div className="mt-2">
        <button onClick={start} disabled={streaming} className="mr-2 px-2 py-1 bg-blue-600 text-white">
          {streaming ? 'Streaming…' : 'Start Stream'}
        </button>
        <button onClick={stop} disabled={!streaming} className="px-2 py-1 bg-gray-600 text-white">
          Stop Stream
        </button>
        {streaming && (
          <a href="/api/stream" target="_blank" rel="noreferrer" className="ml-2 text-sm text-blue-600">Open raw stream</a>
        )}
      </div>
      <div className="mt-2 text-sm">
        <div>Stream status: {streaming ? 'Running' : 'Stopped'}</div>
        {error && <div className="text-red-600">Error: {error}</div>}
      </div>
    </div>
  )
}
