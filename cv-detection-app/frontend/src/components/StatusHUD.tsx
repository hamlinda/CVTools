import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function StatusHUD() {
  const [status, setStatus] = useState<any>(null)

  useEffect(() => {
    axios.get('/api/status').then(r => setStatus(r.data)).catch(() => setStatus(null))
  }, [])

  if (!status) return <div>Loading status...</div>

  return (
    <div className="p-2 border rounded">
      <div>Host: {status.host}</div>
      <div>Port: {status.port}</div>
      <div>Models: {JSON.stringify(status.models)}</div>
    </div>
  )
}
