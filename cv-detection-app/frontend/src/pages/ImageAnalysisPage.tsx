import React, { useState } from 'react'
import ImageUploader from '../components/ImageUploader'
import BoundingBoxCanvas from '../components/BoundingBoxCanvas'

export default function ImageAnalysisPage() {
  const [imageSrc, setImageSrc] = useState<string | null>(null)
  const [detections, setDetections] = useState<any[]>([])

  return (
    <div>
      <ImageUploader onResult={(src, dets) => { setImageSrc(src); setDetections(dets) }} />
      {imageSrc && (
        <div className="mt-4">
          <div style={{ position: 'relative', display: 'inline-block' }}>
            <img src={imageSrc} alt="uploaded" />
            <BoundingBoxCanvas imageSrc={imageSrc} detections={detections} />
          </div>
        </div>
      )}
    </div>
  )
}
