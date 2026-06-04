"""FastAPI application entrypoint for CV detection app.

Handles port negotiation, router registration, logging, and graceful shutdown.
"""
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from backend.routers import image_analysis, webcam_stream, control
from backend.utils.port_finder import find_available_port

load_dotenv()

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT_PREFERRED = int(os.getenv("APP_PORT_PREFERRED", "8080"))
APP_PORT_FALLBACK_RANGE = os.getenv("APP_PORT_FALLBACK_RANGE", "8081,8090")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="CV Detection App")
    app.include_router(image_analysis.router)
    app.include_router(webcam_stream.router)
    app.include_router(control.router)
    return app


def main():
    # negotiate port
    try:
        port = find_available_port(APP_PORT_PREFERRED, APP_PORT_FALLBACK_RANGE)
    except Exception as e:
        logger.exception("Failed to find available port: %s", e)
        sys.exit(1)

    app = create_app()

    # setup graceful shutdown on /api/stop flag
    def _shutdown_check(signum, frame):
        logger.info("Signal received: %s", signum)

    signal.signal(signal.SIGINT, _shutdown_check)
    signal.signal(signal.SIGTERM, _shutdown_check)

    config = uvicorn.Config(app, host=APP_HOST, port=port, log_level=LOG_LEVEL.lower())
    server = uvicorn.Server(config)

    # Run server (blocking)
    server.run()


if __name__ == "__main__":
    main()
