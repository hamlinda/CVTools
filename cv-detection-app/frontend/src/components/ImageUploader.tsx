import React, { useState, useEffect } from 'react'
import api from '../lib/api'
import ErrorPanel from './ErrorPanel'

type Props = { onResult: (src: string, detections: any[]) => void }

export default function ImageUploader({ onResult }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [details, setDetails] = useState<string | null>(null)
  const [ollamaReachable, setOllamaReachable] = useState<boolean | null>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setError(null)
    setDetails(null)
  }

  const checkOllama = async () => {
    try {
      const r = await api.post('/api/ollama/check')
      console.debug('Ollama check response:', r.status, r.data)
      setOllamaReachable(!!r.data.reachable)
      if (r.data && r.data.body) {
        // surface server-side message in details for debugging
        setDetails(typeof r.data.body === 'string' ? r.data.body.slice(0, 2000) : JSON.stringify(r.data.body))
      }
    } catch (e) {
      console.error('Ollama check error', e)
      setOllamaReachable(false)
      setDetails(String(e?.response?.data || e?.message || e))
    }
  }

  const analyze = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setDetails(null)
    const form = new FormData()
    form.append('file', file)
    try {
      // Add a lightweight debug header so the server can echo which client triggered the request
      const resp = await api.post('/api/analyze-image', form, { headers: { 'X-Debug': 'analyze-click' } })
      console.debug('Analyze response:', resp.status, resp.data)
      onResult(preview || '', resp.data.detections || [])
      // show returned request headers (for debugging)
      if (resp.data && resp.data.request_headers) {
        setDetails(JSON.stringify(resp.data.request_headers, null, 2))
      }
    } catch (err: any) {
      console.error('Analyze error', err)
      const serverDetail = err?.response?.data || err?.response?.data?.detail
      const msg = serverDetail || err.message || 'unknown'
      setError('Image analysis failed')
      // Truncate long server responses but keep useful info
      setDetails(typeof msg === 'string' ? msg.slice(0, 2000) : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  // Check Ollama status on component mount so status HUD shows immediately
  useEffect(() => {
    checkOllama()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const clear = () => {
    setFile(null)
    setPreview(null)
    setError(null)
    setDetails(null)
  }

  return (
    <div>
      {!file && <input type="file" accept="image/jpeg" onChange={handleFile} />}

      {preview && (
        <div className="mt-2">
          <div style={{ maxWidth: 800 }}>
            <img src={preview} alt="preview" style={{ maxWidth: '100%' }} />
          </div>

          <div className="mt-2">
            <button onClick={checkOllama} className="mr-2 px-3 py-1 bg-gray-200">Check Ollama</button>
            <button onClick={analyze} disabled={loading || (ollamaReachable === false)} className="mr-2 px-3 py-1 bg-blue-600 text-white">
              {loading ? 'Analyzing…' : 'Analyze Image'}
            </button>
            <button onClick={clear} className="px-3 py-1 bg-gray-300">Cancel</button>
          </div>

          <div className="mt-2 text-sm">
            <div>Ollama reachable: {ollamaReachable === null ? 'unknown' : ollamaReachable ? 'Yes' : 'No'}</div>
          </div>

          <ErrorPanel message={error || undefined} details={details || undefined} onClear={() => { setError(null); setDetails(null) }} />
        </div>
      )}
    </div>
  )
}
