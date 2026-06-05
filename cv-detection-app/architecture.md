# CV Detection App — Architecture

Overview
- Full-stack computer vision application with two primary modes: static image analysis and live webcam stream.
- Backend: Python FastAPI served by Uvicorn. Frontend: Vite + React + Tailwind.

Components
- Backend (`/backend`):
  - `main.py`: app bootstrap, port negotiation, writes `.port_binding` with host/port
  - `routers/`: REST endpoints
    - `/api/analyze-image` (POST): accepts JPEG multipart UploadFile, forwards image+prompt to Ollama, returns JSON with detections
    - `/api/stream` (GET): MJPEG multipart stream, runs YOLO detection + MiDaS depth per-frame, serves annotated frames
    - `/api/status` (GET) and `/api/stop` (POST): health and graceful shutdown control
  - `services/`:
    - `ollama_client.py`: async HTTP client to Ollama (default host: `http://10.0.0.192:11434` for SSH/LAN access)
    - `yolo_detector.py`: ultralytics YOLOv8 wrapper (threadpool for non-blocking inference)
    - `depth_estimator.py`: MiDaS depth estimation
    - `frame_annotator.py`: OpenCV annotations and HUD overlays

- Frontend (`/frontend`): React app with pages/components for image upload, bounding-box canvas, webcam stream viewer, filters, and HUD.

- Launchers & Ops:
  - `start.sh` / `stop.sh` and `docker-compose.yml` for single-command runs.
  - `.port_binding` used by E2E scripts to discover actual bound port when preferred port is in use.

External Services & Network
- Ollama (local or LAN host): HTTP API expected at `OLLAMA_HOST` (env); for SSH sessions use `http://10.0.0.192:11434` to reach the host from the developer machine.
- Client access: app binds `0.0.0.0` and advertises LAN host/IP in logs and `.port_binding` for remote access.

Ports & Endpoints
- App: preferred `8080`, fallback range `8081-8090` (configurable via env)
- Ollama: `11434` (configurable via `OLLAMA_HOST`)
- YOLO/MiDaS: local model files, no external ports

Use Cases
- Static Image Mode: user uploads JPEG → `/api/analyze-image` → backend posts image to Ollama for JSON-labeled detections → frontend overlays bounding boxes and provides class filters.
- Live Webcam Mode: browser connects to `/api/stream` → backend captures webcam frames, runs YOLO & MiDaS, annotates frames, and streams MJPEG to clients for real-time monitoring and per-person distance estimation.

Notes & Operational Considerations
- SSH / LAN: When developing over SSH, `localhost` in server processes may refer to the remote machine; use the LAN IP `10.0.0.192` (or the host's IP) for services like Ollama reachable from the remote environment.
- Dependency requirements: ensure `python-multipart` is installed for multipart form support, and `opencv-python-headless` for server CV operations.
- Ollama readiness: the backend retries Ollama calls but assumes the model endpoint path `/api/generate`; ensure Ollama is reachable and the model is pulled (`ollama pull <model>`) or configure `OLLAMA_HOST` to the correct reachable URL.
- Graceful shutdown: `/api/stop` triggers request flag; main app should observe and gracefully stop Uvicorn.

Connection Map
- Frontend ←(HTTP)-> Backend `/api/*`
- Backend ←(HTTP)-> Ollama `OLLAMA_HOST` (11434)
- Backend → local models (YOLO weights, MiDaS) via filesystem and local inference libraries (ultralytics, torch)

Security
- Run behind network firewalls where appropriate. `APP_SECRET_KEY` used for any future signed endpoints.

Contact
- Repo root: README.md for run instructions and env examples.
