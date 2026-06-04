import { useState } from 'react'

export default function useDetection() {
  const [detections, setDetections] = useState<any[]>([])
  return { detections, setDetections }
}
