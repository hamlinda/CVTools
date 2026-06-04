"""Control router: status and stop endpoints.

Provides `/api/status` returning port, host, model info, and webcam_active flag.
Provides `/api/stop` to trigger graceful shutdown when running non-containerized.
"""
import logging
import os
import socket
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()

PORT_BINDING_PATH = os.getenv("PORT_BINDING_PATH", ".port_binding")
OLLAMA_MODEL_IMAGE = os.getenv("OLLAMA_MODEL_IMAGE")
OLLAMA_MODEL_WEBCAM = os.getenv("OLLAMA_MODEL_WEBCAM")

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
    return {"port": port or 0, "host": host, "models": models, "webcam_active": False}


@router.post("/api/stop")
def stop(background_tasks: BackgroundTasks):
    # request shutdown; main app should observe request_shutdown and stop
    request_shutdown["stop_requested"] = True
    logger.info("Shutdown requested via /api/stop")
    return {"stopping": True}
