# cv_tools — Repository Overview

This repository contains a set of small computer-vision tools and a LAN-aware CV detection web app. The top-level folders are summarized below; see each folder for implementation details and examples.

---

## CV_image

- Solution view & value: A simple, self-contained image face detector that demonstrates using OpenCV's DNN face model for quick local inference. Good for offline image inspection and examples.
- Overview / Core use cases:
  - Detect faces in still images and show bounding boxes.
  - Quick CLI tool for demoing OpenCV DNN usage.
- Technologies used: Python, OpenCV, NumPy, standard library.
- Installation requirements:
  - Python 3.8+
  - `pip install opencv-python numpy` (or system packages that provide these)
- Launch requirements / Usage: CLI
  - Run: `python CV_image/face_detector.py <image_path>`
  - See source: [CV_image/face_detector.py](CV_image/face_detector.py)
- Detailed dependencies:
  - `opencv-python` (for image IO, DNN, drawing)
  - `numpy`
- Architectural implementation:
  - Single-file script. Downloads the Caffe `deploy.prototxt` and `res10_300x300_ssd_iter_140000.caffemodel` on first run and performs DNN forward pass with OpenCV's `dnn` module.
- Disclosure of dependencies:
  - Downloads the OpenCV-provided Caffe model files from GitHub at runtime; network access required for first run.
- API definition set:
  - CLI interface only: input image path, outputs annotated window and console summary of detected faces.

---

## CV_stream

- Solution view & value: A small webcam tracker combining OpenCV face SSD and YOLOv8 targets (person, dog, cell phone). Designed as a runnable demo with an automatic virtualenv bootstrap.
- Overview / Core use cases:
  - Live webcam tracking with toggleable face/YOLO detection.
  - Demonstrates bootstrapped venv creation, model auto-download, and cross-platform camera opening.
- Technologies used: Python, OpenCV, NumPy, Ultralytics (YOLOv8).
- Installation requirements:
  - Python 3.8+
  - The script bootstraps a local virtualenv and installs `opencv-python`, `numpy`, and `ultralytics` when needed. See `CV_stream/requirements.txt`.
- Launch requirements / Usage:
  - Run: `python CV_stream/tracker.py` (the script bootstraps a `.venv` on first run)
  - See source: [CV_stream/tracker.py](CV_stream/tracker.py)
- Detailed dependencies (see `CV_stream/requirements*.txt`):
  - `opencv-python>=4.8`
  - `numpy>=1.24`
  - `ultralytics>=8.0`
  - `requests` (client variant)
  - `flask` (server variant)
- Architectural implementation:
  - Single-process interactive application. Loads face SSD (Caffe) and YOLOv8 model (downloads on first run) and draws HUD/annotations in an OpenCV window.
- Disclosure of dependencies:
  - Downloads model weights (Caffe prototxt + caffemodel, YOLO `yolov8n.pt`) on first run if missing.
- API definition set:
  - CLI / interactive controls: `q` quit, `f` toggle face detection, `y` toggle YOLO detection.

---

## cv-detection-app

- Solution view & value: A LAN-aware web application combining LAN-hosted Ollama-based still-image analysis and a local YOLOv8 + MiDaS-powered webcam streaming pipeline. Provides both an SPA frontend and a FastAPI backend to support image analysis and MJPEG webcam streaming.
- Overview / Core use cases:
  - Static image analysis using Ollama multimodal models (JSON output for boxes/labels).
  - Live webcam streaming with local YOLOv8 detection and MiDaS depth estimates.
  - Docker Compose friendly for redistribution.
- Technologies used:
  - Backend: Python, FastAPI, Uvicorn, httpx, python-dotenv
  - Models: Ultralytics YOLOv8, MiDaS (via torch.hub)
  - Frontend: Vite, React/TypeScript (see `cv-detection-app/frontend`)
  - External: Ollama (external HTTP service for multimodal inference)
- Installation requirements:
  - Python 3.11+
  - Node.js 18+ and npm (for frontend development)
  - Ollama instance reachable on the LAN (set `OLLAMA_HOST`)
  - Optional GPU + CUDA/ROCm for accelerated model inference
  - See `cv-detection-app/README.md` for quick-start instructions.
- Launch requirements / Usage:
  - Backend dependencies: `pip install -r cv-detection-app/backend/requirements.txt`
  - Frontend: `cd cv-detection-app/frontend && npm install && npm run dev`
  - Start both: `./cv-detection-app/start.sh` or via Docker Compose: `docker compose up --build`
  - Main backend entrypoint: [cv-detection-app/backend/main.py](cv-detection-app/backend/main.py)
- Detailed dependencies (selected from `cv-detection-app/backend/requirements.txt`):
  - `fastapi>=0.95.0`
  - `uvicorn[standard]>=0.22.0`
  - `python-dotenv>=1.0.0`
  - `httpx>=0.24.0`
  - `opencv-python-headless>=4.7.0`
  - `python-multipart>=0.0.5`
  - `ultralytics>=8.0.0`
  - `torch>=2.0.0`, `torchvision>=0.15.0`, `timm>=0.9.0`
  - `pytest>=7.0.0` (for tests)
- Architectural implementation:
  - FastAPI backend that negotiates an available port (writes selected port to `.port_binding`) and exposes REST endpoints for image analysis and a streaming MJPEG endpoint for webcam.
  - Background task periodically probes Ollama health and updates an internal health state.
  - Service modules encapsulate model clients: `ollama_client`, `yolo_detector`, `depth_estimator`, and `frame_annotator`.
  - Frontend (Vite + React) connects to backend APIs for static image upload and reads the MJPEG stream for live webcam.
- Disclosure of dependencies:
  - Requires access to an Ollama instance (not bundled). Ollama models must be pulled on the Ollama host (e.g. `ollama pull llava:13b`).
  - Several models are downloaded or loaded at runtime (YOLO weights, MiDaS via `torch.hub`). GPU acceleration optional but recommended for performance.
- API definition set (backend endpoints):
  - `GET /api/status` — return port, host, configured models, Ollama health and webcam probe
  - `POST /api/stop` — request graceful shutdown (sets a flag)
  - `POST /api/ollama/check` — on-demand Ollama health probe
  - `GET /api/ollama/models` — proxy list of models available on Ollama host
  - `GET /api/webcam/source` — probe webcam source availability
  - `POST /api/analyze-image` — multipart JPEG upload; returns structured `detections` JSON (uses Ollama)
  - `GET /api/stream` — MJPEG multipart stream of annotated frames (YOLO + depth)

---

## How this README was generated

This root README summarizes the per-folder implementations and the source files present in the repository. For full details, examples, environment variables and troubleshooting, consult the per-folder documentation and source files, for example:

- [cv-detection-app/README.md](cv-detection-app/README.md)
- [CV_image/face_detector.py](CV_image/face_detector.py)
- [CV_stream/tracker.py](CV_stream/tracker.py)

If you'd like, I can expand any section with commands, example env files, or generate a consolidated `.env.example`.
