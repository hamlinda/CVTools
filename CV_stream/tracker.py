#!/usr/bin/env python3
"""
Webcam tracker — faces, dogs, and cell phones with confidence scores.

Self-bootstrapping: run with any Python 3.8+ and it will create a local
venv, install its own dependencies, and re-launch itself automatically.

    python tracker.py          # or: python3 tracker.py
    ./tracker.py               # macOS / Linux (chmod +x tracker.py)

Controls (while the window is open):
    q  — quit
    f  — toggle face detection
    y  — toggle YOLO detection  (person / dog / cell phone)
"""

# ============================================================
# BOOTSTRAP — must run before any third-party imports
# ============================================================
import sys
import os
import subprocess
from pathlib import Path

VENV_DIR  = Path(__file__).parent / ".venv"
REQUIRES  = ["opencv-python>=4.8", "numpy>=1.24", "ultralytics>=8.0"]
_SENTINEL = "__CV_BOOTSTRAPPED__"

def _bootstrap() -> None:
    """Create venv + install deps, then re-exec this script inside it."""
    import venv as _venv

    print("[ bootstrap ] Setting up virtual environment …")
    _venv.create(str(VENV_DIR), with_pip=True, clear=False)

    # Locate the venv python / pip executables
    if sys.platform == "win32":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
        venv_pip    = VENV_DIR / "Scripts" / "pip.exe"
    else:
        venv_python = VENV_DIR / "bin" / "python3"
        venv_pip    = VENV_DIR / "bin" / "pip"

    print("[ bootstrap ] Installing dependencies (first run only) …")
    subprocess.check_call(
        [str(venv_pip), "install", "--quiet", "--upgrade", "pip"],
        stderr=subprocess.DEVNULL,
    )
    subprocess.check_call([str(venv_pip), "install", "--quiet"] + REQUIRES)
    print("[ bootstrap ] Done — launching tracker …\n")

    # Re-exec inside the venv; sentinel prevents infinite loops
    env = os.environ.copy()
    env[_SENTINEL] = "1"
    os.execve(str(venv_python), [str(venv_python), __file__] + sys.argv[1:], env)


def _needs_bootstrap() -> bool:
    """True when we're not already inside the managed venv."""
    if os.environ.get(_SENTINEL):
        return False  # already bootstrapped
    try:
        import cv2          # noqa: F401
        import ultralytics  # noqa: F401
        import numpy        # noqa: F401
        return False        # all deps present in current interpreter
    except ImportError:
        return True


if _needs_bootstrap():
    _bootstrap()
    sys.exit(1)  # unreachable — execve replaces the process

# ============================================================
# Normal imports (deps guaranteed to be available here)
# ============================================================
import urllib.request
import urllib.error
import platform

import cv2
import numpy as np

# ============================================================
# Configuration
# ============================================================

COLORS: dict[str, tuple[int, int, int]] = {
    "face":       ( 30, 130, 255),   # orange
    "person":     ( 50, 210,  50),   # lime green
    "dog":        (  0, 165, 255),   # amber
    "cell phone": (220,   0, 220),   # magenta
}

# COCO class IDs for YOLOv8
YOLO_TARGETS: dict[int, str] = {0: "person", 16: "dog", 67: "cell phone"}

FACE_PROTOTXT_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/"
    "samples/dnn/face_detector/deploy.prototxt"
)
FACE_CAFFEMODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/"
    "dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)
MODEL_DIR = Path(__file__).parent / "models"

# ============================================================
# Helpers
# ============================================================

def _download(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {dest.name} …", end=" ", flush=True)
    try:
        urllib.request.urlretrieve(url, dest)
        print("done")
    except urllib.error.URLError as exc:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed for {url}: {exc}") from exc


def load_face_net() -> cv2.dnn.Net:
    prototxt    = MODEL_DIR / "deploy.prototxt"
    caffemodel  = MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
    _download(FACE_PROTOTXT_URL,   prototxt)
    _download(FACE_CAFFEMODEL_URL, caffemodel)
    return cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))


def detect_faces(
    net: cv2.dnn.Net,
    frame: np.ndarray,
    threshold: float = 0.50,
) -> list[tuple[int, int, int, int, float]]:
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)),
        1.0, (300, 300), (104.0, 177.0, 123.0), swapRB=False,
    )
    net.setInput(blob)
    dets = net.forward()
    out = []
    for i in range(dets.shape[2]):
        conf = float(dets[0, 0, i, 2])
        if conf < threshold:
            continue
        box = (dets[0, 0, i, 3:7] * [w, h, w, h]).astype(int)
        x1 = max(0, box[0]); y1 = max(0, box[1])
        x2 = min(w - 1, box[2]); y2 = min(h - 1, box[3])
        out.append((x1, y1, x2, y2, conf))
    return out


def draw_box(
    frame: np.ndarray,
    x1: int, y1: int, x2: int, y2: int,
    label: str,
    color: tuple[int, int, int],
) -> None:
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    tw = len(label) * 9 + 8
    ty = max(y1 - 22, 0)
    cv2.rectangle(frame, (x1, ty), (x1 + tw, y1), color, -1)
    cv2.putText(
        frame, label, (x1 + 4, y1 - 5),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA,
    )


def open_camera(preferred_index: int = 0) -> cv2.VideoCapture:
    """Try camera indices 0-3 across platform-specific backends."""
    backends = (
        [cv2.CAP_AVFOUNDATION]   if platform.system() == "Darwin"  else
        [cv2.CAP_DSHOW, cv2.CAP_MSMF] if platform.system() == "Windows" else
        [cv2.CAP_V4L2, cv2.CAP_ANY]
    )
    for idx in range(preferred_index, preferred_index + 4):
        for backend in backends:
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                return cap
            cap.release()
    raise RuntimeError(
        "No webcam found. Check that a camera is connected and not in use."
    )

# ============================================================
# Main
# ============================================================

def main() -> None:
    # ---- face detector ----
    print("Loading face detector …")
    try:
        face_net = load_face_net()
    except Exception as exc:
        sys.exit(f"Fatal: could not load face model — {exc}")

    # ---- YOLO ----
    yolo_model = None
    try:
        from ultralytics import YOLO  # type: ignore
        print("Loading YOLOv8n (downloads on first run) …")
        yolo_model = YOLO("yolov8n.pt")
        print("  → YOLO ready")
    except Exception as exc:
        print(f"  WARNING: YOLO unavailable ({exc}); dog/phone detection disabled.")

    # ---- camera ----
    print("Opening camera …")
    try:
        cap = open_camera()
    except RuntimeError as exc:
        sys.exit(f"Fatal: {exc}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  → {actual_w}×{actual_h}")

    face_on = True
    yolo_on = True

    print("\nRunning — q quit  |  f toggle faces  |  y toggle YOLO\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed — exiting.")
            break

        display = frame.copy()

        # -- face detection --
        if face_on:
            for x1, y1, x2, y2, conf in detect_faces(face_net, frame):
                draw_box(display, x1, y1, x2, y2,
                         f"face {conf:.0%}", COLORS["face"])

        # -- YOLO --
        if yolo_on and yolo_model is not None:
            results = yolo_model(frame, verbose=False, conf=0.40)[0]
            for box in results.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in YOLO_TARGETS:
                    continue
                conf = float(box.conf[0])
                name = YOLO_TARGETS[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                draw_box(display, x1, y1, x2, y2,
                         f"{name} {conf:.0%}", COLORS[name])

        # -- HUD --
        hud = [
            f"faces : {'ON' if face_on else 'off'}  (f)",
            f"YOLO  : {'ON' if yolo_on else 'off'}  (y)  — person | dog | cell phone",
            "quit  : q",
        ]
        for i, line in enumerate(hud):
            cv2.putText(display, line, (10, 22 + i * 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (210, 210, 210), 1, cv2.LINE_AA)

        cv2.imshow("CV Stream — Tracker", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:   # q or Esc
            break
        elif key == ord("f"):
            face_on = not face_on
            print(f"Faces {'ON' if face_on else 'off'}")
        elif key == ord("y"):
            yolo_on = not yolo_on
            print(f"YOLO  {'ON' if yolo_on else 'off'}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
