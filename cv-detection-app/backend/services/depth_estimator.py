"""MiDaS depth estimation wrapper.

Provides `DepthEstimator` which loads a MiDaS model via `torch.hub` and exposes
async methods to compute a depth map and estimate distance at a normalized
coordinate. Runs heavy work in a ThreadPoolExecutor to avoid blocking asyncio.

Note: MiDaS returns relative depth; a configurable `DEPTH_SCALE` environment
variable is applied to convert to approximate meters. For accurate metric
distance, calibrate `DEPTH_SCALE` for your camera and scene.
"""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

DEPTH_MODEL = os.getenv("DEPTH_MODEL", "MiDaS_small")
DEPTH_ENABLED = os.getenv("DEPTH_ENABLED", "true").lower() in ("1", "true", "yes")
DEPTH_SCALE = float(os.getenv("DEPTH_SCALE", "1.0"))

logger = logging.getLogger(__name__)


class DepthEstimator:
    def __init__(self, model_name: str = DEPTH_MODEL, scale: float = DEPTH_SCALE) -> None:
        if not DEPTH_ENABLED:
            raise RuntimeError("Depth estimation is disabled via DEPTH_ENABLED=false")

        self.model_name = model_name
        self.scale = float(scale)
        self._device = "cpu"
        self._model = None
        self._transform = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._loaded = False

        # lazy load to avoid heavy imports at module import time
        self._load_model()

    def _load_model(self) -> None:
        try:
            import torch

            # Use torch.hub to load MiDaS models
            model_type = "MiDaS_small" if self.model_name.lower().startswith("midas") else self.model_name
            self._model = torch.hub.load("intel-isl/MiDaS", model_type)
            self._model.to(self._device)
            self._model.eval()

            # default transform
            transform = torch.hub.load("intel-isl/MiDaS", "transforms")
            if model_type == "MiDaS_small":
                self._transform = transform.small_transform
            else:
                self._transform = transform.default_transform

            self._loaded = True
            logger.info("Loaded MiDaS model %s", model_type)
        except Exception as e:
            logger.exception("Failed to load MiDaS model: %s", e)
            raise

    async def compute_depth_map(self, frame: np.ndarray) -> np.ndarray:
        """Compute a depth map for the given BGR frame (numpy array).

        Returns a 2D numpy array of depth values (float), same HxW as the input.
        """
        if not self._loaded:
            raise RuntimeError("Depth model not loaded")

        loop = asyncio.get_running_loop()
        depth_map = await loop.run_in_executor(self._executor, self._compute_sync, frame)
        return depth_map

    def _compute_sync(self, frame: np.ndarray) -> np.ndarray:
        import torch

        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        input_tensor = self._transform(img).unsqueeze(0)
        input_tensor = input_tensor.to(self._device)

        with torch.no_grad():
            prediction = self._model(input_tensor)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=img.shape[:2], mode="bicubic", align_corners=False
            ).squeeze().cpu().numpy()

        # MiDaS returns relative depth (higher = closer or further depending on model).
        # We'll normalize to 0..1 and apply scale to yield approximate meters.
        norm = prediction - np.min(prediction)
        if np.max(norm) > 0:
            norm = norm / np.max(norm)
        depth_m = norm * self.scale
        return depth_m

    async def get_distance_at(self, frame: np.ndarray, x_norm: float, y_norm: float) -> float:
        """Return estimated distance in meters at normalized coordinates (x_norm, y_norm).

        x_norm, y_norm should be in 0..1 (relative to image width and height).
        """
        h, w = frame.shape[0], frame.shape[1]
        cx = min(max(int(x_norm * w), 0), w - 1)
        cy = min(max(int(y_norm * h), 0), h - 1)

        depth_map = await self.compute_depth_map(frame)
        # safe guard
        if cy >= depth_map.shape[0] or cx >= depth_map.shape[1]:
            return float("nan")

        return float(depth_map[cy, cx])


__all__ = ["DepthEstimator"]
