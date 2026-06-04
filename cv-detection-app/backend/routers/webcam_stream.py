"""Webcam MJPEG streaming router.

GET /api/stream
Streams annotated MJPEG frames using YOLOv8 and MiDaS depth estimation.
"""
import asyncio
import logging
import os
import time
from typing import AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

from backend.services.yolo_detector import YoloDetector
from backend.services.depth_estimator import DepthEstimator
from backend.services.frame_annotator import annotate_frame

logger = logging.getLogger(__name__)

router = APIRouter()

WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
WEBCAM_FRAME_WIDTH = int(os.getenv("WEBCAM_FRAME_WIDTH", "1280"))
WEBCAM_FRAME_HEIGHT = int(os.getenv("WEBCAM_FRAME_HEIGHT", "720"))
WEBCAM_TARGET_FPS = int(os.getenv("WEBCAM_TARGET_FPS", "15"))
YOLO_MAX_PERSONS = int(os.getenv("YOLO_MAX_PERSONS", "10"))


def _encode_mjpeg(frame: np.ndarray) -> bytes:
    ret, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ret:
        raise RuntimeError("Failed to encode frame")
    return buf.tobytes()


@router.get("/api/stream")
async def stream_webcam():
    # Open webcam
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        raise HTTPException(status_code=503, detail="Webcam not available")

    # configure capture
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WEBCAM_FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_FRAME_HEIGHT)
    target_fps = WEBCAM_TARGET_FPS

    detector = YoloDetector()
    depth = None
    try:
        depth = DepthEstimator()
    except Exception:
        logger.warning("Depth estimator not available; streaming without distances")

    boundary = b"frame"

    async def generator() -> AsyncGenerator[bytes, None]:
        try:
            last = 0.0
            while True:
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame from webcam")
                    await asyncio.sleep(0.1)
                    continue

                # run detection (async)
                try:
                    detections = await detector.detect(frame)
                except Exception as e:
                    logger.exception("YOLO detection failed: %s", e)
                    detections = []

                # compute depth map once per frame if available
                depth_map = None
                if depth is not None:
                    try:
                        depth_map = await depth.compute_depth_map(frame)
                    except Exception as e:
                        logger.exception("Depth computation failed: %s", e)
                        depth_map = None

                # annotate
                annotated = annotate_frame(frame, detections, depth_map=depth_map, max_persons=YOLO_MAX_PERSONS)

                # encode
                try:
                    jpg = _encode_mjpeg(annotated)
                except Exception:
                    logger.exception("Failed to encode annotated frame")
                    await asyncio.sleep(0.05)
                    continue

                # build multipart chunk
                chunk = b"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % (boundary, len(jpg)) + jpg + b"\r\n"
                yield chunk

                # throttle to target fps
                elapsed = time.time() - t0
                delay = max(0, (1.0 / target_fps) - elapsed)
                if delay > 0:
                    await asyncio.sleep(delay)

        finally:
            try:
                cap.release()
            except Exception:
                pass

    return StreamingResponse(generator(), media_type=f"multipart/x-mixed-replace; boundary={boundary.decode()}")
