"""Router for static image analysis using Ollama.

POST /api/analyze-image
Accepts a JPEG image (multipart form) and returns structured detections.
"""
import base64
import io
import logging
import time
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv()

from backend.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter()


class Detection(BaseModel):
    label: str
    bbox: List[float]  # [x1,y1,x2,y2] normalized
    confidence: float


class AnalyzeImageResponse(BaseModel):
    detections: List[Detection]
    elapsed_ms: int
    attempts: int = 1


MAX_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_CONTENTS = {"image/jpeg", "image/jpg"}


@router.post("/api/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(file: UploadFile = File(...)):
    # validate content type
    content_type = file.content_type or ""
    if content_type.lower() not in ALLOWED_CONTENTS:
        raise HTTPException(status_code=400, detail="Only JPEG images are supported")

    contents = await file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    # encode base64 without data: prefix
    img_b64 = base64.b64encode(contents).decode("ascii")

    prompt = (
        "List all people and objects visible. For each, provide: label, bounding box as [x1, y1, x2, y2] "
        "normalized 0-1, and confidence if available. Return JSON only."
    )

    client = OllamaClient()

    start = time.time()
    try:
        parsed = await client.analyze_image(image_base64=img_b64, prompt=prompt)
    except Exception as e:
        logger.exception("Ollama analyze_image failed: %s", e)
        raise HTTPException(status_code=502, detail="Inference failed")
    elapsed_ms = int((time.time() - start) * 1000)

    # parsed is expected to be a JSON object; attempt to extract 'detections' or accept direct list
    detections_raw = parsed.get("detections") if isinstance(parsed, dict) else parsed
    if detections_raw is None:
        # try to recover if model returned top-level list
        if isinstance(parsed, list):
            detections_raw = parsed
        else:
            raise HTTPException(status_code=502, detail="Malformed model response")

    detections = []
    attempts = parsed.get("attempts", 1) if isinstance(parsed, dict) else 1

    for item in detections_raw:
        try:
            label = item.get("label") if isinstance(item, dict) else None
            bbox = item.get("bbox") if isinstance(item, dict) else None
            conf = float(item.get("confidence", 0.0)) if isinstance(item, dict) else 0.0
            if label is None or bbox is None:
                continue
            # ensure bbox is 4 floats
            if len(bbox) != 4:
                continue
            detections.append({"label": label, "bbox": [float(x) for x in bbox], "confidence": conf})
        except Exception:
            continue

    return {"detections": detections, "elapsed_ms": elapsed_ms, "attempts": attempts}
