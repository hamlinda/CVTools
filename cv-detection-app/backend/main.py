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
import httpx
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

    # schedule a non-blocking Ollama health checker on startup
    async def _ollama_health_checker_periodic():
        host = os.getenv("OLLAMA_HOST", "http://10.0.0.192:11434")
        endpoint = f"{host.rstrip('/')}/api/generate"
        retry_delay = int(os.getenv("LAN_RETRY_DELAY_MS", "500")) / 1000.0
        first_check = True
        # run an initial check immediately, then periodic checks
        while True:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    # Use POST probe to verify the generate endpoint accepts requests.
                    # Only 2xx will be considered healthy.
                    model = os.getenv("OLLAMA_MODEL_IMAGE")
                    probe_payload = {"model": model, "prompt": "healthcheck"} if model else {"prompt": "healthcheck"}
                    resp = await client.post(endpoint, json=probe_payload)
                    healthy = 200 <= resp.status_code < 300
                    control.update_ollama_health(healthy, resp.status_code)
                    logger.info("Ollama health check: %s %s (healthy=%s)", endpoint, resp.status_code, healthy)
                    if first_check and not healthy:
                        logger.warning(
                            "Ollama generate endpoint reachable but not healthy (status %s). If no model is loaded, run: `ollama pull <model>` on host %s or adjust OLLAMA_HOST/OLLAMA_MODEL_IMAGE.",
                            resp.status_code,
                            host,
                        )
            except Exception as exc:
                control.update_ollama_health(False, None)
                if first_check:
                    logger.error(
                        "Ollama health probe failed on startup: %s. If Ollama runs on the host, ensure you can reach %s from this machine and that models are pulled (e.g. `ollama pull <model>`).",
                        exc,
                        host,
                    )
                else:
                    logger.debug("Ollama health check failed: %s", exc)
            first_check = False
            await asyncio.sleep(max(1.0, retry_delay))

    # register startup event to spawn background task
    @app.on_event("startup")
    async def _startup_tasks():
        # create task and keep reference so we can cancel it on shutdown
        app.state.ollama_health_task = asyncio.create_task(_ollama_health_checker_periodic())

    @app.on_event("shutdown")
    async def _shutdown_tasks():
        task = getattr(app.state, "ollama_health_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Ollama health checker cancelled on shutdown")

    # setup graceful shutdown on OS signals
    def _shutdown_check(signum, frame):
        logger.info("Signal received: %s", signum)

    signal.signal(signal.SIGINT, _shutdown_check)
    signal.signal(signal.SIGTERM, _shutdown_check)

    async def _run_server_and_watch():
        config = uvicorn.Config(app, host=APP_HOST, port=port, log_level=LOG_LEVEL.lower())
        server = uvicorn.Server(config)

        # start server in background task so we can observe control flags
        serve_task = asyncio.create_task(server.serve())

        try:
            # monitor for /api/stop requests and set server.should_exit to trigger graceful shutdown
            while not server.should_exit:
                if control.request_shutdown.get("stop_requested"):
                    logger.info("/api/stop requested — initiating graceful shutdown")
                    server.should_exit = True
                    break
                await asyncio.sleep(0.5)

            # wait for server to finish
            await serve_task
        finally:
            if not serve_task.done():
                serve_task.cancel()

    # Run the server inside asyncio event loop so we can control shutdown
    try:
        asyncio.run(_run_server_and_watch())
    except Exception as e:
        logger.exception("Server runtime error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
