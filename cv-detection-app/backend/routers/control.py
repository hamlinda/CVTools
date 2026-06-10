"""Control router: status and stop endpoints.

Provides `/api/status` returning port, host, model info, and webcam_active flag.
Provides `/api/stop` to trigger graceful shutdown when running non-containerized.
"""
import logging
import os
import socket
import cv2
from dotenv import load_dotenv
import time
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
import httpx
import asyncio
from backend.services import ollama_client as _ollama_client
from backend.services.ollama_client import OllamaClient

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()

PORT_BINDING_PATH = os.getenv("PORT_BINDING_PATH", ".port_binding")
OLLAMA_MODEL_IMAGE = os.getenv("OLLAMA_MODEL_IMAGE")
OLLAMA_MODEL_WEBCAM = os.getenv("OLLAMA_MODEL_WEBCAM")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://10.0.0.192:11434")
OLLAMA_ENDPOINT = f"{OLLAMA_HOST.rstrip('/')}/api/generate"

# Health state for Ollama connectivity; updated by a background checker
OLLAMA_HEALTH = {
    "reachable": False,
    "status_code": None,
    "last_checked": None,
    "endpoint": OLLAMA_ENDPOINT,
}

# A simple flag used to request shutdown from /api/stop. The FastAPI app should
# monitor this value or import `request_shutdown` to trigger server shutdown.
request_shutdown = {"stop_requested": False}


def _get_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass
    return ip


class StatusResponse(BaseModel):
    port: int
    host: str
    models: dict
    webcam_active: bool = False
    ollama: dict | None = None


@router.get("/api/status", response_model=StatusResponse)
def status():
    port = None
    try:
        if os.path.exists(PORT_BINDING_PATH):
            with open(PORT_BINDING_PATH, "r") as f:
                port = int(f.read().strip() or 0)
    except Exception:
        port = None

    host = _get_lan_ip()
    models = {"ollama_image": OLLAMA_MODEL_IMAGE, "ollama_webcam": OLLAMA_MODEL_WEBCAM}
    return {"port": port or 0, "host": host, "models": models, "webcam_active": False, "ollama": OLLAMA_HEALTH}


@router.post("/api/stop")
def stop(background_tasks: BackgroundTasks):
    # request shutdown; main app should observe request_shutdown and stop
    request_shutdown["stop_requested"] = True
    logger.info("Shutdown requested via /api/stop")
    return {"stopping": True}


@router.post("/api/ollama/check")
async def ollama_check():
    """Perform an on-demand health check against the configured Ollama endpoint
    and update the shared `OLLAMA_HEALTH` structure.
    """
    try:
        # Use a longer read timeout for health probes to accommodate slower Ollama responses
        timeout = httpx.Timeout(15.0, read=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Prefer configured env var, fall back to Ollama client module default
            model = OLLAMA_MODEL_IMAGE or getattr(_ollama_client, "OLLAMA_MODEL_IMAGE", None)
            payload = {"model": model, "prompt": "healthcheck"} if model else {"prompt": "healthcheck"}

            # Use a streaming request and read only the first N lines / bytes so we don't block
            collected = []
            total_bytes = 0
            status_code = None
            try:
                async with client.stream("POST", OLLAMA_ENDPOINT, json=payload) as resp:
                    status_code = resp.status_code
                    reachable = 200 <= status_code < 300
                    # read up to 50 lines or 20KB
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        collected.append(line)
                        total_bytes += len(line)
                        # stop early if we have enough data
                        if len(collected) >= 50 or total_bytes > 20000:
                            break
            except Exception as e:
                # streaming/read could timeout or fail
                logger.exception("Error while streaming from Ollama:")
                update_ollama_health(False, None)
                return {"reachable": False, "status_code": None, "error": str(e), "exception": repr(e)}

            body_text = "\n".join(collected)
            parsed_result = None
            try:
                parsed_result = OllamaClient._safe_parse_json(body_text)
            except Exception:
                parsed_result = None

            update_ollama_health(bool(reachable), status_code)
            OLLAMA_HEALTH["result"] = parsed_result if parsed_result is not None else (body_text[:2000] if body_text else None)
            return {"reachable": bool(reachable), "status_code": status_code, "result": parsed_result, "body": body_text}
    except Exception as e:
        # Log full exception for debugging and return repr so callers see details
        logger.exception("Error during /api/ollama/check:")
        update_ollama_health(False, None)
        return {"reachable": False, "status_code": None, "error": str(e), "exception": repr(e)}


@router.get("/api/ollama/models")
async def ollama_models():
    """Return the list of models available on the configured Ollama host."""
    models_url = f"{OLLAMA_HOST.rstrip('/')}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(models_url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


def update_ollama_health(reachable: bool, status_code: int | None):
    OLLAMA_HEALTH["reachable"] = bool(reachable)
    OLLAMA_HEALTH["status_code"] = int(status_code) if status_code is not None else None
    OLLAMA_HEALTH["last_checked"] = int(time.time())


# Webcam config probe
WEBCAM_SOURCE = os.getenv("WEBCAM_SOURCE")
try:
    WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
except Exception:
    WEBCAM_INDEX = 0
VIDEO_DEVICE = os.getenv("VIDEO_DEVICE")


@router.get("/api/webcam/source")
def webcam_source():
    """Return the configured webcam source and whether it can be opened by OpenCV.

    Response includes:
    - `source`: string (env `WEBCAM_SOURCE` or `index:<n>`)
    - `index`: integer index tested
    - `device`: raw `VIDEO_DEVICE` env value if set
    - `available`: boolean indicating whether OpenCV could open the source
    - `error`: present when opening failed
    """
    source = WEBCAM_SOURCE if WEBCAM_SOURCE else f"index:{WEBCAM_INDEX}"
    idx = WEBCAM_INDEX
    device = VIDEO_DEVICE
    available = False
    error = None
    try:
        if WEBCAM_SOURCE:
            cap = cv2.VideoCapture(WEBCAM_SOURCE)
        else:
            cap = cv2.VideoCapture(idx)
        available = bool(cap.isOpened())
        try:
            cap.release()
        except Exception:
            pass
    except Exception as e:
        available = False
        error = str(e)

    return {"source": source, "index": idx, "device": device, "available": available, "error": error}
