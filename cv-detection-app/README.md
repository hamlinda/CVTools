# CV Detection App

This repository provides a LAN-aware computer vision detection application with two modes: static image analysis (via Ollama) and live webcam stream (YOLOv8 + MiDaS). It is designed to run on a LAN-connected Linux host and is resilient to port conflicts.

**Quick start**

1. Copy `.env.example` to `.env` and edit as needed.
2. Install backend deps:

```bash
python3 -m pip install -r backend/requirements.txt
```

3. Install frontend deps and run dev server:

```bash
cd frontend
npm install
npm run dev
```

4. Start the app (both backend and frontend):

```bash
./start.sh
```

Or use Docker Compose:

```bash
docker compose up --build
```

**How to verify Ollama connectivity**

Check that Ollama is reachable at `OLLAMA_HOST` (default `http://localhost:11434`) and that the desired models are pulled:

```bash
ollama pull llava:13b
ollama pull moondream
curl ${OLLAMA_HOST}/v1/models
```

## Running with Docker (recommended for redistribution)

This repository supplies a `docker-compose.yml` that starts an Ollama container together with the backend. The Ollama image is configurable via the `OLLAMA_IMAGE` environment variable; by default the compose file references `ollama/ollama:latest` (replace with the official image you prefer).

Quick start using Docker Compose:

```bash
# build and start Ollama + backend in background
docker compose up --build -d

# backend will be available on the port in APP_PORT_PREFERRED (default 8080)
curl http://localhost:8080/api/status
```

Helper script:

```bash
./start-with-docker.sh
```

Notes:
- The backend is configured by the compose file to use `http://ollama:11434` as `OLLAMA_HOST` so it talks to the Ollama container by service name.
- If you already run Ollama elsewhere, you can omit the `ollama` service and set `OLLAMA_HOST` to the desired host:port.
```

**Active port identification**

If the preferred port is in use, the app will bind an available port in `APP_PORT_FALLBACK_RANGE` and write the selected port number to `.port_binding` in the project root. Check that file or call `GET /api/status`.

---

## Architecture Decision Record (ADR)

- Why Ollama for still-image analysis: Ollama's multimodal models (llava) are convenient for free-form image descriptions and JSON responses; they allow higher-level reasoning about an image compared to pure object detectors. Good for one-off static images where latency is acceptable.
- Why YOLOv8 + MiDaS for webcam: YOLOv8 runs locally with low latency and predictable FPS; MiDaS provides fast monocular depth estimates for distance approximation. This avoids repeated network hops to Ollama for every frame.
- Why FastAPI + MJPEG: FastAPI offers async-friendly HTTP endpoints and easy integration with streaming responses. MJPEG provides broad browser compatibility without complex WebSocket frame handling for simple overlays.
- LAN deployment: bind to `0.0.0.0` so other LAN devices can reach the service; use retry and async inference to handle 1–25ms LAN latency gracefully.

---

## Prerequisites

- Python 3.11+
- Node 18+ and npm (for frontend dev)
- Ollama installed locally or accessible on the LAN
- (Optional) GPU + CUDA/ROCm for accelerated YOLO/MiDaS

### Pull recommended Ollama models

```bash
ollama pull llava:13b
ollama pull moondream
```

---

## Environment Configuration

See `.env.example` for full variables. Copy to `.env` and modify.

---

## Model Reference

See `.env.example` for model names. Expected VRAM and inference times vary by hardware. Use `moondream` or `llava:7b` for webcam to reduce latency.

---

## Troubleshooting

- Port conflicts: check `.port_binding` and `GET /api/status`.
- Webcam not detected: ensure `/dev/video*` accessible and `WEBCAM_INDEX` correct.
- Ollama model not found: run `ollama pull <model>`.
- Blank bounding boxes: model may have returned malformed JSON; review logs and retry.

---

## Tests

Run backend tests with:

```bash
pytest -q
```
