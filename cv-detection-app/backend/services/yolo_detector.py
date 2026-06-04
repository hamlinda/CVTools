"""YOLOv8 detector wrapper.

Provides an async-safe `YoloDetector` that runs YOLOv8 inference in a thread
pool to avoid blocking the event loop. Returns normalized bounding boxes
in the form [x1, y1, x2, y2] with coordinates normalized to 0..1.
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import numpy as np
from dotenv import load_dotenv

load_dotenv()

YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
YOLO_CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.45"))
YOLO_MAX_PERSONS = int(os.getenv("YOLO_MAX_PERSONS", "10"))

logger = logging.getLogger(__name__)


class YoloDetector:
    def __init__(self, model_path: str = YOLO_MODEL, conf_thresh: float = YOLO_CONFIDENCE_THRESHOLD) -> None:
        # import here to keep import-time dependency optional for other tools
        try:
            from ultralytics import YOLO
        except Exception as e:  # pragma: no cover - import/runtime
            raise RuntimeError("ultralytics YOLO package not installed") from e

        self.model_path = model_path
        self.conf_thresh = float(conf_thresh)
        self._model = YOLO(self.model_path)
        # ThreadPoolExecutor for running blocking model.predict
        self._executor = ThreadPoolExecutor(max_workers=1)

    async def detect(self, frame: np.ndarray) -> List[Dict]:
        """Run detection on a single BGR frame (numpy array).

        Returns a list of detections with normalized bbox coordinates.
        Each detection dict contains: class_id, label, confidence, bbox
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._executor, self._predict_sync, frame)
        return result

    def _predict_sync(self, frame: np.ndarray) -> List[Dict]:
        # model.predict accepts RGB or BGR depending on version; ultralytics handles np arrays
        results = self._model.predict(frame, conf=self.conf_thresh, verbose=False)
        out: List[Dict] = []
        if not results:
            return out

        # results is a list (per batch); we process the first
        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None:
            return out

        img_h, img_w = frame.shape[0], frame.shape[1]

        # boxes.xyxy, boxes.conf, boxes.cls
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.array(boxes.xyxy)
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.array(boxes.conf)
        clsids = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.array(boxes.cls)

        names = getattr(self._model, "names", {})

        for (x1, y1, x2, y2), conf, cls in zip(xyxy, confs, clsids):
            # normalize
            nx1 = float(x1) / float(img_w)
            ny1 = float(y1) / float(img_h)
            nx2 = float(x2) / float(img_w)
            ny2 = float(y2) / float(img_h)

            label = names.get(int(cls), str(int(cls)))

            out.append({
                "class_id": int(cls),
                "label": label,
                "confidence": float(conf),
                "bbox": [nx1, ny1, nx2, ny2],
            })

        return out


__all__ = ["YoloDetector"]
