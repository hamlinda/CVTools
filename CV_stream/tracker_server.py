#!/usr/bin/env python3
"""
CV Stream — inference server (runs on the Linux host via SSH).

No webcam or display required.  Receives JPEG frames over HTTP from
the Windows client, runs face + YOLO detection, and returns annotated
JPEG frames.

Start:
    python tracker_server.py [--host 0.0.0.0] [--port 5000]
    sh run_server.sh
"""

# ============================================================
# BOOTSTRAP — must run before any third-party imports
# ============================================================
import sys, os, subprocess
from pathlib import Path

VENV_DIR = Path(__file__).parent / ".venv"
REQUIRES = ["opencv-python>=4.8", "numpy>=1.24", "ultralytics>=8.0", "flask>=3.0"]
_SENTINEL = "__CV_SERVER_BOOT__"


def _bootstrap() -> None:
    import venv as _v
    print("[ bootstrap ] Setting up virtual environment …")
    _v.create(str(VENV_DIR), with_pip=True, clear=False)
    if sys.platform == "win32":
        pip = VENV_DIR / "Scripts" / "pip.exe"
        py  = VENV_DIR / "Scripts" / "python.exe"
    else:
        pip = VENV_DIR / "bin" / "pip"
        py  = VENV_DIR / "bin" / "python3"
    subprocess.check_call([str(pip), "install", "--quiet", "--upgrade", "pip"],
                          stderr=subprocess.DEVNULL)
    subprocess.check_call([str(pip), "install", "--quiet"] + REQUIRES)
    print("[ bootstrap ] Done — launching server …\n")
    env = {**os.environ, _SENTINEL: "1"}
    if sys.platform == "win32":
        sys.exit(subprocess.run([str(py), __file__] + sys.argv[1:], env=env).returncode)
    os.execve(str(py), [str(py), __file__] + sys.argv[1:], env)


if not os.environ.get(_SENTINEL):
    try:
        import cv2, ultralytics, numpy, flask  # noqa: F401
    except ImportError:
        _bootstrap()
        sys.exit(1)  # unreachable; safety net

# ============================================================
# Normal imports (deps guaranteed available here)
# ============================================================
import argparse
import io
import urllib.request
import urllib.error

import cv2
import numpy as np
from flask import Flask, request, send_file, jsonify

# ============================================================
# Configuration
# ============================================================
COLORS: dict[str, tuple[int, int, int]] = {
    "face":       ( 30, 130, 255),
    "person":     ( 50, 210,  50),
    "dog":        (  0, 165, 255),
    "cell phone": (220,   0, 220),
}
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
# Model helpers (same logic as tracker.py)
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
    proto  = MODEL_DIR / "deploy.prototxt"
    caffe  = MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel"
    _download(FACE_PROTOTXT_URL,   proto)
    _download(FACE_CAFFEMODEL_URL, caffe)
    return cv2.dnn.readNetFromCaffe(str(proto), str(caffe))


def detect_faces(
    net: cv2.dnn.Net,
    frame: np.ndarray,
    threshold: float = 0.50,
) -> list[tuple[int, int, int, int, float]]:
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)),
        1.0, (300, 300), (104., 177., 123.), swapRB=False,
    )
    net.setInput(blob)
    dets = net.forward()
    out = []
    for i in range(dets.shape[2]):
        conf = float(dets[0, 0, i, 2])
        if conf < threshold:
            continue
        box = (dets[0, 0, i, 3:7] * [w, h, w, h]).astype(int)
        x1, y1 = max(0, box[0]), max(0, box[1])
        x2, y2 = min(w - 1, box[2]), min(h - 1, box[3])
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
    cv2.putText(frame, label, (x1 + 4, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)


# ============================================================
# Flask app
# ============================================================
app = Flask(__name__)

_face_net   = None
_yolo_model = None


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "face":   _face_net is not None,
        "yolo":   _yolo_model is not None,
    })


@app.route("/detect", methods=["POST"])
def detect():
    data = request.get_data()
    if not data:
        return "No image data", 400

    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return "Invalid image", 400

    enable_faces = request.args.get("faces", "1") != "0"
    enable_yolo  = request.args.get("yolo",  "1") != "0"

    out = frame.copy()

    if enable_faces and _face_net is not None:
        for x1, y1, x2, y2, conf in detect_faces(_face_net, frame):
            draw_box(out, x1, y1, x2, y2, f"face {conf:.0%}", COLORS["face"])

    if enable_yolo and _yolo_model is not None:
        results = _yolo_model(frame, verbose=False, conf=0.40)[0]
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in YOLO_TARGETS:
                continue
            conf = float(box.conf[0])
            name = YOLO_TARGETS[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            draw_box(out, x1, y1, x2, y2, f"{name} {conf:.0%}", COLORS[name])

    _, jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return send_file(io.BytesIO(jpeg.tobytes()), mimetype="image/jpeg")


# ============================================================
# Main
# ============================================================

def main() -> None:
    global _face_net, _yolo_model

    parser = argparse.ArgumentParser(description="CV Stream inference server")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind address (default: 0.0.0.0 = all interfaces)")
    parser.add_argument("--port", type=int, default=5000,
                        help="Port (default: 5000)")
    args = parser.parse_args()

    print("Loading face detector …")
    try:
        _face_net = load_face_net()
        print("  → face detector ready")
    except Exception as exc:
        print(f"  WARNING: face detector unavailable — {exc}")

    print("Loading YOLOv8n (downloads ~6 MB on first run) …")
    try:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")
        print("  → YOLO ready")
    except Exception as exc:
        print(f"  WARNING: YOLO unavailable — {exc}")

    print(f"\nServer listening on http://{args.host}:{args.port}")
    print("Point your Windows client at this server's LAN IP.\n")

    # threaded=False: single-threaded — safe because one client sends one frame at a time
    app.run(host=args.host, port=args.port, debug=False, threaded=False)


if __name__ == "__main__":
    main()
