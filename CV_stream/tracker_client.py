#!/usr/bin/env python3
"""
CV Stream — Windows client.

Captures the local webcam, streams JPEG frames to the Linux inference
server, and displays the annotated result in a local window.
No ML models are needed on the Windows side.

Usage:
    python tracker_client.py [SERVER_URL]
    python tracker_client.py http://192.168.1.100:5000

Or set the environment variable before running:
    set CV_SERVER=http://192.168.1.100:5000
    python tracker_client.py

Controls (while the window is open):
    q / Esc  — quit
    f        — toggle face detection
    y        — toggle YOLO detection  (person / dog / cell phone)
"""

# ============================================================
# BOOTSTRAP — must run before any third-party imports
# ============================================================
import sys, os, subprocess
from pathlib import Path

VENV_DIR = Path(__file__).parent / ".venv"
REQUIRES = ["opencv-python>=4.8", "numpy>=1.24", "requests>=2.28"]
_SENTINEL = "__CV_CLIENT_BOOT__"


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
    print("[ bootstrap ] Done — launching client …\n")
    env = {**os.environ, _SENTINEL: "1"}
    if sys.platform == "win32":
        sys.exit(subprocess.run([str(py), __file__] + sys.argv[1:], env=env).returncode)
    os.execve(str(py), [str(py), __file__] + sys.argv[1:], env)


if not os.environ.get(_SENTINEL):
    try:
        import cv2, numpy, requests  # noqa: F401
    except ImportError:
        _bootstrap()
        sys.exit(1)  # unreachable; safety net

# ============================================================
# Normal imports (deps guaranteed available here)
# ============================================================
import platform
import queue
import threading
import time
from typing import Optional

import cv2
import numpy as np
import requests as _requests

# ============================================================
# Configuration
# ============================================================
DEFAULT_SERVER = os.environ.get("CV_SERVER", "http://localhost:5000")
JPEG_QUALITY   = 75   # lower = smaller frame payload = lower latency
STALE_TIMEOUT  = 3.0  # seconds before showing "no server" warning


# ============================================================
# Camera
# ============================================================

def open_camera(preferred_index: int = 0) -> cv2.VideoCapture:
    """Try camera indices 0-3 across platform-specific backends."""
    backends = (
        [cv2.CAP_AVFOUNDATION]         if platform.system() == "Darwin"  else
        [cv2.CAP_DSHOW, cv2.CAP_MSMF]  if platform.system() == "Windows" else
        [cv2.CAP_V4L2,  cv2.CAP_ANY]
    )
    for idx in range(preferred_index, preferred_index + 4):
        for backend in backends:
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                return cap
            cap.release()
    raise RuntimeError("No webcam found. Check that a camera is connected and not in use.")


# ============================================================
# Background inference thread
# ============================================================

def inference_worker(
    server_url: str,
    send_q: "queue.Queue[Optional[np.ndarray]]",
    flags: dict,                        # {"faces": bool, "yolo": bool}  — read under GIL
    result_state: list,                 # [latest_annotated | None, last_result_time]
    result_lock: threading.Lock,
    stop_event: threading.Event,
) -> None:
    """Sends frames to the server; updates result_state with the annotated reply."""
    session = _requests.Session()
    while not stop_event.is_set():
        try:
            frame = send_q.get(timeout=0.5)
        except queue.Empty:
            continue
        if frame is None:
            return
        try:
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            params = {
                "faces": "1" if flags["faces"] else "0",
                "yolo":  "1" if flags["yolo"]  else "0",
            }
            resp = session.post(
                f"{server_url}/detect",
                data=jpeg.tobytes(),
                params=params,
                headers={"Content-Type": "image/jpeg"},
                timeout=2.0,
            )
            if resp.ok:
                annotated = cv2.imdecode(
                    np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)
                if annotated is not None:
                    with result_lock:
                        result_state[0] = annotated
                        result_state[1] = time.monotonic()
        except _requests.exceptions.ConnectionError:
            time.sleep(0.2)   # brief back-off while server is unreachable
        except Exception as exc:
            print(f"  [client] {exc}")


# ============================================================
# HUD overlay
# ============================================================

def draw_hud(
    frame: np.ndarray,
    flags: dict,
    connected: bool,
    server_url: str,
) -> None:
    dot_color = (0, 200, 0) if connected else (0, 60, 220)
    cv2.circle(frame, (frame.shape[1] - 15, 15), 8, dot_color, -1)

    status = "connected" if connected else "NO SERVER — check address"
    lines = [
        f"server: {status}  ({server_url})",
        f"faces : {'ON' if flags['faces'] else 'off'}  (f)",
        f"YOLO  : {'ON' if flags['yolo']  else 'off'}  (y)  — person | dog | cell phone",
        "quit  : q / Esc",
    ]
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (10, 22 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (210, 210, 210), 1, cv2.LINE_AA)

    if not connected:
        msg = "WAITING FOR SERVER"
        (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cx = (frame.shape[1] - tw) // 2
        cy = frame.shape[0] // 2
        cv2.putText(frame, msg, (cx, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 60, 220), 2, cv2.LINE_AA)


# ============================================================
# Main
# ============================================================

def main() -> None:
    server_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER
    print(f"Server: {server_url}")
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

    flags = {"faces": True, "yolo": True}

    # Shared state: [latest_annotated_frame | None, timestamp_of_last_result]
    result_state: list = [None, 0.0]
    result_lock  = threading.Lock()
    stop_event   = threading.Event()

    send_q: "queue.Queue[Optional[np.ndarray]]" = queue.Queue(maxsize=2)

    worker = threading.Thread(
        target=inference_worker,
        args=(server_url, send_q, flags, result_state, result_lock, stop_event),
        daemon=True,
    )
    worker.start()

    last_display: Optional[np.ndarray] = None
    print("\nRunning — q/Esc quit  |  f toggle faces  |  y toggle YOLO\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed — exiting.")
            break

        # Enqueue for inference; silently drop if worker hasn't caught up
        try:
            send_q.put_nowait(frame)
        except queue.Full:
            pass

        # Pull latest annotated frame if one arrived
        with result_lock:
            if result_state[0] is not None:
                last_display = result_state[0]
                result_state[0] = None
            last_t = result_state[1]

        connected = (last_t > 0) and (time.monotonic() - last_t < STALE_TIMEOUT)
        display   = (last_display if last_display is not None else frame).copy()
        draw_hud(display, flags, connected, server_url)

        cv2.imshow("CV Stream — Client", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break
        elif key == ord("f"):
            flags["faces"] = not flags["faces"]
            print(f"Faces {'ON' if flags['faces'] else 'off'}")
        elif key == ord("y"):
            flags["yolo"] = not flags["yolo"]
            print(f"YOLO  {'ON' if flags['yolo'] else 'off'}")

    stop_event.set()
    try:
        send_q.put_nowait(None)
    except queue.Full:
        pass
    cap.release()
    cv2.destroyAllWindows()
    worker.join(timeout=2.0)


if __name__ == "__main__":
    main()
