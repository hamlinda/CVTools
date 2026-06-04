"""Frame annotator utilities for drawing detections and HUD on OpenCV frames.

Functions:
  - annotate_frame(frame, detections, depth_map=None, max_persons=3) -> annotated_frame

`detections` is a list of dicts: { 'class_id', 'label', 'confidence', 'bbox':[x1,y1,x2,y2] }
where bbox coordinates are normalized 0..1.
"""
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


COLOR_PERSON = (0, 0, 255)  # red BGR
COLOR_VEHICLE = (255, 0, 0)  # blue
COLOR_ANIMAL = (0, 255, 0)  # green
COLOR_OTHER = (192, 192, 192)  # light gray
HUD_BG = (0, 0, 0)


def _choose_color(label: str) -> Tuple[int, int, int]:
    l = label.lower()
    if "person" in l or "people" in l or l == "person":
        return COLOR_PERSON
    if any(x in l for x in ("car", "truck", "vehicle", "bus", "van")):
        return COLOR_VEHICLE
    if any(x in l for x in ("dog", "cat", "animal", "horse")):
        return COLOR_ANIMAL
    return COLOR_OTHER


def annotate_frame(frame: np.ndarray, detections: List[Dict], depth_map: Optional[np.ndarray] = None, max_persons: int = 3) -> np.ndarray:
    """Draw bounding boxes, labels, confidences, distances, and HUD on the frame.

    Args:
        frame: BGR image numpy array (H,W,3)
        detections: list of detection dicts (normalized bbox coords)
        depth_map: optional HxW float array with distance in meters
        max_persons: threshold for person count HUD (e.g., show 3+)

    Returns:
        Annotated BGR image (copy of input)
    """
    out = frame.copy()
    h, w = out.shape[:2]

    person_count = 0

    for det in detections:
        bbox = det.get("bbox", [0, 0, 0, 0])
        x1 = int(max(min(bbox[0], 1.0), 0.0) * w)
        y1 = int(max(min(bbox[1], 1.0), 0.0) * h)
        x2 = int(max(min(bbox[2], 1.0), 0.0) * w)
        y2 = int(max(min(bbox[3], 1.0), 0.0) * h)

        label = det.get("label", "obj")
        conf = det.get("confidence", 0.0)

        color = _choose_color(label)

        # draw rectangle
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness=2)

        # text: label + confidence
        txt = f"{label} {conf:.2f}"
        txt_sz, _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        txt_w, txt_h = txt_sz

        # background for text
        cv2.rectangle(out, (x1, y1 - txt_h - 6), (x1 + txt_w + 6, y1), color, thickness=-1)
        cv2.putText(out, txt, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # distance if depth_map provided: sample centroid
        if depth_map is not None:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            # clamp
            cx = max(0, min(cx, depth_map.shape[1] - 1))
            cy = max(0, min(cy, depth_map.shape[0] - 1))
            dist = float(depth_map[cy, cx])
            dist_txt = f"{dist:.1f}m"
            dt_sz, _ = cv2.getTextSize(dist_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            dt_w, dt_h = dt_sz
            cv2.rectangle(out, (x2 - dt_w - 6, y2), (x2, y2 + dt_h + 6), HUD_BG, thickness=-1)
            cv2.putText(out, dist_txt, (x2 - dt_w - 3, y2 + dt_h + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if label.lower() == "person" or "person" in label.lower():
            person_count += 1

    # draw person count HUD
    hud_text = f"👤 {person_count} / {max_persons if person_count < max_persons else str(max_persons) + '+'}"
    hud_sz, _ = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    hud_w, hud_h = hud_sz
    pad = 10
    cv2.rectangle(out, (pad, pad), (pad + hud_w + 12, pad + hud_h + 12), HUD_BG, thickness=-1)
    cv2.putText(out, hud_text, (pad + 6, pad + hud_h), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    return out


__all__ = ["annotate_frame"]
