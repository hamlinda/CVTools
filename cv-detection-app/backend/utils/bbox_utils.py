"""Bounding box normalization utilities."""

from typing import Tuple, List


def normalize_bbox(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> List[float]:
    return [x1 / width, y1 / height, x2 / width, y2 / height]


def denormalize_bbox(bbox: List[float], width: int, height: int) -> Tuple[int, int, int, int]:
    x1 = int(bbox[0] * width)
    y1 = int(bbox[1] * height)
    x2 = int(bbox[2] * width)
    y2 = int(bbox[3] * height)
    return x1, y1, x2, y2


__all__ = ["normalize_bbox", "denormalize_bbox"]
