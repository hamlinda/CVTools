import React from 'react'

type Props = {
  title?: string
  message?: string
  details?: string
  onClear?: () => void
}

export default function ErrorPanel({ title = 'Error', message, details, onClear }: Props) {
  if (!message && !details) return null
  return (
    <div className="mt-3 p-3 border rounded bg-red-50 text-sm">
      <div className="font-semibold text-red-700">{title}</div>
      {message && <div className="mt-1">{message}</div>}
      {details && <pre className="mt-2 whitespace-pre-wrap text-xs bg-white p-2 rounded">{details}</pre>}
      {onClear && (
        <div className="mt-2">
          <button onClick={onClear} className="px-2 py-1 bg-red-600 text-white">Dismiss</button>
        </div>
      )}
    </div>
  )
}
