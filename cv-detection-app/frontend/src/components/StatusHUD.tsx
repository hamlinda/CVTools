import React, { useEffect, useState } from 'react'
import api from '../lib/api'

export default function StatusHUD() {
  const [status, setStatus] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)

  const fetchStatus = async () => {
    setLoading(true)
    try {
      const r = await api.get('/api/status')
      setStatus(r.data)
    } catch (err) {
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const t = setInterval(fetchStatus, 5000)
    return () => clearInterval(t)
  }, [])

  const runOllamaCheck = async () => {
    setChecking(true)
    try {
      await api.post('/api/ollama/check')
      await fetchStatus()
    } catch (e) {
      // ignore
    } finally {
      setChecking(false)
    }
  }

  const [modelsList, setModelsList] = useState<string[] | null>(null)
  const fetchModels = async () => {
    try {
      const r = await api.get('/api/ollama/models')
      if (r.data && Array.isArray(r.data)) setModelsList(r.data.map((m: any) => m.name || JSON.stringify(m)))
      else if (r.data && r.data.models) setModelsList(r.data.models)
      else setModelsList([JSON.stringify(r.data)])
    } catch (e) {
      setModelsList([`error: ${e?.message ?? e}`])
    }
  }

  if (loading) return <div>Loading status...</div>

  return (
    <div className="p-3 border rounded bg-white">
      <div className="mb-2 font-semibold">Application Status</div>
      <div className="text-sm">
        <div><strong>Host:</strong> {status?.host ?? '—'}</div>
        <div><strong>Port:</strong> {status?.port ?? '—'}</div>
        <div><strong>Webcam active:</strong> {status?.webcam_active ? 'Yes' : 'No'}</div>
        <div><strong>Models:</strong> {status?.models ? JSON.stringify(status.models) : '—'}</div>
      </div>

      <div className="mt-3 font-semibold">Ollama Connectivity</div>
      <div className="text-sm">
        <div><strong>Endpoint:</strong> {status?.ollama?.endpoint ?? '—'}</div>
        <div><strong>Reachable:</strong> {status?.ollama?.reachable ? 'Yes' : 'No'}</div>
        <div><strong>Status code:</strong> {status?.ollama?.status_code ?? '—'}</div>
        <div><strong>Last checked:</strong> {status?.ollama?.last_checked ? new Date(status.ollama.last_checked * 1000).toLocaleString() : '—'}</div>
      </div>

      {status?.ollama?.result && (
        <div className="mt-3">
          <div className="font-semibold">Ollama Last Result</div>
          <pre className="text-xs bg-gray-50 p-2 rounded max-h-40 overflow-auto">{typeof status.ollama.result === 'string' ? status.ollama.result : JSON.stringify(status.ollama.result, null, 2)}</pre>
        </div>
      )}

      <div className="mt-3">
        <button onClick={runOllamaCheck} disabled={checking} className="px-3 py-1 bg-blue-600 text-white mr-2">
          {checking ? 'Checking…' : 'Run Ollama Check'}
        </button>
        <button onClick={fetchStatus} className="px-3 py-1 bg-gray-200 mr-2">Refresh</button>
        <button onClick={fetchModels} className="px-3 py-1 bg-gray-200">Fetch Ollama Models</button>
      </div>

      {modelsList && (
        <div className="mt-3">
          <div className="font-semibold">Available Ollama Models</div>
          <ul className="text-sm list-disc list-inside">
            {modelsList.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

    </div>
  )
}
