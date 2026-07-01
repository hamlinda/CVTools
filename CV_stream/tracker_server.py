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
    if sys.platform == "win32":
        pip = VENV_DIR / "Scripts" / "pip.exe"
        py  = VENV_DIR / "Scripts" / "python.exe"
    else:
        pip = VENV_DIR / "bin" / "pip"
        py  = VENV_DIR / "bin" / "python3"

    if not py.exists() or not pip.exists():
        print("[ bootstrap ] Setting up virtual environment …")
        _v.create(str(VENV_DIR), with_pip=True, clear=False)

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


@app.route("/")
def index():
    face_status = "Ready" if _face_net is not None else "Unavailable"
    face_class = "ready" if _face_net is not None else "missing"
    yolo_status = "Ready" if _yolo_model is not None else "Unavailable"
    yolo_class = "ready" if _yolo_model is not None else "missing"
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV Stream - Inference Server</title>
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 28, 45, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-green: #10b981;
            --accent-green-glow: rgba(16, 185, 129, 0.2);
            --accent-red: #ef4444;
            --accent-red-glow: rgba(239, 68, 68, 0.2);
            --accent-blue: #3b82f6;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.05) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
        }

        .container {
            width: 100%;
            max-width: 680px;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
            animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 32px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 24px;
        }

        .title-group h1 {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .title-group p {
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--accent-green-glow);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--accent-green);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 600;
        }

        .status-badge .dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        .section-title {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            margin-bottom: 16px;
            font-weight: 600;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin-bottom: 32px;
        }

        .card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            transition: all 0.2s ease;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.15);
            background: rgba(255, 255, 255, 0.04);
            transform: translateY(-2px);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .card-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .model-status {
            font-size: 12px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        }

        .model-status.ready {
            background: var(--accent-green-glow);
            color: var(--accent-green);
        }

        .model-status.missing {
            background: var(--accent-red-glow);
            color: var(--accent-red);
        }

        .card-desc {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        .endpoints-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 32px;
        }

        .endpoint-row {
            display: flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 14px 20px;
            gap: 16px;
        }

        .method {
            font-size: 12px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 6px;
            min-width: 64px;
            text-align: center;
        }

        .method.post {
            background: rgba(59, 130, 246, 0.15);
            color: var(--accent-blue);
        }

        .method.get {
            background: rgba(16, 185, 129, 0.15);
            color: var(--accent-green);
        }

        .path {
            font-family: monospace;
            font-size: 14px;
            font-weight: 600;
            color: #c7d2fe;
            flex-grow: 1;
        }

        .endpoint-desc {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .info-footer {
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            border-top: 1px solid var(--border-color);
            padding-top: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="title-group">
                <h1>CV Stream Inference Server</h1>
                <p>Linux Host Inference Engine</p>
            </div>
            <div class="status-badge">
                <span class="dot"></span>
                <span>Online</span>
            </div>
        </header>

        <h2 class="section-title">Models Status</h2>
        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Face Detector</span>
                    <span class="model-status __FACE_CLASS__">__FACE_STATUS__</span>
                </div>
                <p class="card-desc">OpenCV DNN ResNet SSD model for fast face bounding box detection.</p>
            </div>
            <div class="card">
                <div class="card-header">
                    <span class="card-title">YOLOv8 Object Detector</span>
                    <span class="model-status __YOLO_CLASS__">__YOLO_STATUS__</span>
                </div>
                <p class="card-desc">Ultralytics YOLOv8n model optimized for person, dog, and cell phone tracking.</p>
            </div>
        </div>

        <h2 class="section-title">API Endpoints</h2>
        <div class="endpoints-list">
            <div class="endpoint-row">
                <span class="method get">GET</span>
                <span class="path">/health</span>
                <span class="endpoint-desc">Check service health & models availability</span>
            </div>
            <div class="endpoint-row">
                <span class="method post">POST</span>
                <span class="path">/detect</span>
                <span class="endpoint-desc">Accepts raw JPEG data, returns annotated JPEG</span>
            </div>
        </div>

        <div class="info-footer">
            <p>Connect your CV Stream client to: <code style="color: #fff; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; font-family: monospace;">http://&lt;SERVER_IP&gt;:5000</code></p>
        </div>
    </div>
</body>
</html>"""
    return html.replace("__FACE_STATUS__", face_status).replace("__FACE_CLASS__", face_class).replace("__YOLO_STATUS__", yolo_status).replace("__YOLO_CLASS__", yolo_class)

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
