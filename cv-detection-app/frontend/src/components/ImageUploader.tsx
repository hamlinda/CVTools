import React from 'react'
import axios from 'axios'

type Props = { onResult: (src: string, detections: any[]) => void }

export default function ImageUploader({ onResult }: Props) {
  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const form = new FormData()
    form.append('file', f)
    const resp = await axios.post('/api/analyze-image', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    const blob = URL.createObjectURL(f)
    onResult(blob, resp.data.detections || [])
  }

  return (
    <div>
      <input type="file" accept="image/jpeg" onChange={handleFile} />
    </div>
  )
}
