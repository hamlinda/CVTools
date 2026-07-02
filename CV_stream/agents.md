# Agent Guidelines & Component Architecture: CV_stream

This guide details the self-bootstrapping webcam tracking system, client-server design patterns, API endpoints, and dashboard designs for the `CV_stream` service.

---

## 1. Sub-Service Overview

The `CV_stream` service provides real-time webcam tracking using OpenCV SSD (faces) and YOLOv8 (person, dog, cell phone targets). It is designed to run in both standalone local mode and network client-server mode (offloading GPU-accelerated inference to a Linux server).

### Network Data flow
```
                  [Client Machine]                         [Server Machine]
    ┌──────────────────────────────────────────┐     ┌────────────────────────────┐
    │  [Camera Cap] ──> [Enqueues Frame]       │     │                            │
    │                        │                 │     │                            │
    │                  (bg thread)             │     │                            │
    │                        ▼                 │     │                            │
    │                  [HTTP POST JPEG]  ──────┼────┼─> [Flask POST /detect]     │
    │                                          │     │       │                    │
    │                                          │     │       ├─> Run SSD (Face)   │
    │                                          │     │       ├─> Run YOLOv8       │
    │                                          │     │       ├─> Draw Box Overlays│
    │                  [Receives JPEG]   <─────┼─────┼── [JPEG Image Return]      │
    │                        │                 │     │                            │
    │                        ▼                 │     │                            │
    │                  [Render Frame]          │     │                            │
    └──────────────────────────────────────────┘     └────────────────────────────┘
```

---

## 2. Self-Bootstrapping Environment

All three Python entries (`tracker.py`, `tracker_server.py`, `tracker_client.py`) implement a self-bootstrapping script header.
- **Bootstrapping Process**:
  - The script checks if it is running in its local virtualenv using a sentinel environment variable (`__CV_BOOTSTRAPPED__`, `__CV_SERVER_BOOT__`, or `__CV_CLIENT_BOOT__`).
  - If the sentinel is missing, it dynamically compiles a virtualenv at `CV_stream/.venv/`.
  - It updates `pip` and installs requirements (`opencv-python>=4.8`, `numpy>=1.24`, `ultralytics>=8.0`, `flask>=3.0`, `requests>=2.28`).
  - It then executes `os.execve` or `subprocess.run` to replace the current interpreter process with the virtualenv’s python binary, forwarding all arguments.

---

## 3. Component Details & Protocols

### A. Standalone Mode (`tracker.py`)
- Standard webcam tracking loop displaying a window via `cv2.imshow`.
- Intercepts keyboard events on the GUI window:
  - `q` or `Esc`: Release camera resources and close GUI.
  - `f`: Toggle face SSD model.
  - `y`: Toggle YOLOv8 detector.
- Displays a real-time status HUD in the top-left corner of the window.

### B. Inference Server (`tracker_server.py`)
Exposes a lightweight Flask interface on port `5000`:
- **`GET /`**: Renders a premium, glassmorphic dark-mode web monitoring dashboard.
  - **Aesthetics**: Tailored CSS containing rich colors (`--bg-color: #0b0f19`, `--card-bg: rgba(22, 28, 45, 0.6)`), rounded cards with subtle drop shadows (`box-shadow`), layout grid system (`display: grid`), and custom animation transitions.
  - **Status Indicator**: An active, pulsing indicator dot displaying connection states (using a CSS pulse animation that scales and changes opacity).
  - **Models Info**: Interactive cards representing loaded states of Face Detector and YOLOv8.
- **`GET /health`**: Returns JSON details: `{"status": "ok", "face": true, "yolo": true}`.
- **`POST /detect`**:
  - Receives raw binary image data (`request.get_data()`) sent by the client.
  - Decodes BGR frames using `cv2.imdecode(..., cv2.IMREAD_COLOR)`.
  - Runs face SSD and YOLOv8 detections based on request query variables (`?faces=1&yolo=1`).
  - Encodes the result as a JPEG (`quality=85`) and streams it back using `send_file`.
  - **Single Threaded**: Runs with `threaded=False` on the Flask engine, as one client uploads sequential frames synchronously.

### C. Client Mode (`tracker_client.py`)
Designed to stream frames from local webcams to a remote server without needing local ML weights or GPU capability.
- **Threading Layout**:
  - **Main Thread**: Controls webcam acquisition via `cv2.VideoCapture` and GUI loop. Pushes new frames to `send_q` (Queue size restricted to `2` to prevent latency drift).
  - **Inference Thread**: Pulls frames from `send_q`, encodes them to JPEG (`quality=75` to minimize payload footprint), calls Flask server `POST /detect`, decodes returned frames, and updates `result_state`.
- **Latency & Reliability Features**:
  - If a frame request fails, the thread sleeps `200ms` before retrying to prevent hammering the network.
  - Displays a "WAITING FOR SERVER" error screen if `result_state` timestamp updates stop for more than `3.0` seconds (`STALE_TIMEOUT`).

### D. Process Orchestration (Scripts)
- **`run_server.sh`**:
  - Launces the Flask server in the background using `nohup` (`nohup python3 tracker_server.py > server.log 2>&1 &`).
  - Writes the running background process ID (PID) to `server.pid`.
- **`shutdown.sh`**:
  - Reads `server.pid` and executes a graceful `kill` instruction.
  - Cleans up temporary pid markers and releases socket binds.

---

## 4. Coding Conventions

- **Thread Safety**: Access to shared variables (like `result_state`) in multi-threaded environments must be wrapped inside a `threading.Lock()` context manager.
- **Robust Camera Inits**: Implement fallback camera discovery loop across multiple backends (such as `cv2.CAP_AVFOUNDATION` on macOS, `cv2.CAP_DSHOW` or `cv2.CAP_MSMF` on Windows, and `cv2.CAP_V4L2` on Linux) to prevent startup failures.
- **Resource Disposals**: Cameras and window resources must be released inside `finally` blocks using `cap.release()` and `cv2.destroyAllWindows()`.
