import React, { useEffect, useRef } from 'react'

type Det = { bbox: number[]; label: string; confidence: number }

export default function BoundingBoxCanvas({ imageSrc, detections }: { imageSrc: string; detections: Det[] }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => {
    const img = imgRef.current
    const canvas = canvasRef.current
    if (!img || !canvas) return
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    detections.forEach(d => {
      const [x1, y1, x2, y2] = d.bbox
      ctx.strokeStyle = d.label.toLowerCase().includes('person') ? 'red' : 'gray'
      ctx.lineWidth = 2
      ctx.strokeRect(x1 * canvas.width, y1 * canvas.height, (x2 - x1) * canvas.width, (y2 - y1) * canvas.height)
      ctx.fillStyle = 'rgba(0,0,0,0.5)'
      ctx.fillRect(x1 * canvas.width, y1 * canvas.height - 18, 100, 18)
      ctx.fillStyle = 'white'
      ctx.fillText(`${d.label} ${d.confidence.toFixed(2)}`, x1 * canvas.width + 4, y1 * canvas.height - 4)
    })
  }, [imageSrc, detections])

  return (
    <div style={{ position: 'absolute', left: 0, top: 0 }}>
      <img ref={imgRef} src={imageSrc} alt="uploaded" style={{ display: 'block' }} />
      <canvas ref={canvasRef} style={{ position: 'absolute', left: 0, top: 0 }} />
    </div>
  )
}
