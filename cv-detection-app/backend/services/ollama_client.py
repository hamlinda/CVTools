"""Async Ollama HTTP client with retry and timeout handling.

Loads configuration from environment via python-dotenv. Provides `analyze_image`
which posts a prompt and base64-encoded image to the Ollama HTTP endpoint and
returns a parsed JSON response. Retries are controlled by environment variables
`LAN_RETRY_ATTEMPTS` and `LAN_RETRY_DELAY_MS`.
"""
import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv


load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://10.0.0.192:11434")
OLLAMA_MODEL_IMAGE = os.getenv("OLLAMA_MODEL_IMAGE")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
LAN_RETRY_ATTEMPTS = int(os.getenv("LAN_RETRY_ATTEMPTS", "3"))
LAN_RETRY_DELAY_MS = int(os.getenv("LAN_RETRY_DELAY_MS", "500"))

if not OLLAMA_MODEL_IMAGE:
    raise EnvironmentError("Missing required environment variable: OLLAMA_MODEL_IMAGE")

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL_IMAGE, timeout: int = OLLAMA_TIMEOUT_SECONDS,
                 retries: int = LAN_RETRY_ATTEMPTS, retry_delay_ms: int = LAN_RETRY_DELAY_MS) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = max(1, int(retries))
        self.retry_delay_ms = int(retry_delay_ms)

    def _endpoint(self) -> str:
        # Ollama commonly exposes a generate endpoint; leave path configurable if needed
        return f"{self.host}/api/generate"

    @staticmethod
    def _safe_parse_json(text: str) -> Dict[str, Any]:
        # Fast-path: fully-formed JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Robust extraction: find the last complete JSON object by scanning
        # the text and matching balanced braces while respecting string
        # quoting and escapes. This handles NDJSON-style streams or
        # concatenated JSON objects without a clear delimiter.
        candidates = []
        depth = 0
        in_string = False
        escape = False
        start_idx = None
        for i, ch in enumerate(text):
            if ch == '\\' and in_string:
                escape = not escape
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                # reset escape flag after toggling string state
                escape = False
                continue
            # reset escape for non-backslash characters
            escape = False

            if in_string:
                continue

            if ch == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        # record a complete top-level JSON object
                        candidates.append(text[start_idx : i + 1])
                        start_idx = None

        # Try parsing the last complete object if any
        if candidates:
            last = candidates[-1]
            try:
                return json.loads(last)
            except json.JSONDecodeError:
                # fallthrough to error below
                pass

        # As a final attempt, try to salvage by looking for the last '{' and
        # attempting to parse from there (legacy fallback).
        last_open = text.rfind('{')
        while last_open != -1:
            candidate = text[last_open:]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                last_open = text.rfind('{', 0, last_open)

        raise ValueError("Failed to parse JSON response from Ollama")

    async def analyze_image(self, image_base64: str, prompt: str) -> Dict[str, Any]:
        """Send image + prompt to Ollama and return parsed JSON results.

        Args:
            image_base64: base64-encoded JPEG image string (data without data: prefix)
            prompt: textual prompt instructing the model to return JSON with boxes

        Returns:
            Parsed JSON dict returned by the model.

        Raises:
            RuntimeError on repeated failures.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            # include image as a field the backend can use; Ollama prompt formats vary,
            # callers can embed the base64 string into the prompt if required.
            "image_base64": image_base64,
        }

        url = self._endpoint()

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                # Use a streaming request to handle NDJSON or chunked responses.
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug("STREAM POST %s attempt=%d payload_keys=%s", url, attempt, list(payload.keys()))
                    async with client.stream("POST", url, json=payload) as resp:
                        resp.raise_for_status()

                        # Collect lines and attempt to parse JSON events as they arrive.
                        last_parsed: Optional[Dict[str, Any]] = None
                        collected_lines: list[str] = []
                        # For streaming tokenized responses, aggregate 'response' fields
                        # across events to reconstruct the full model output.
                        aggregated_response = ""

                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            collected_lines.append(line)

                            # Try to parse the line as JSON; many Ollama streams emit
                            # small JSON events where the `response` field is incremental.
                            candidate = None
                            try:
                                candidate = self._safe_parse_json(line)
                                last_parsed = candidate
                            except Exception:
                                # line may contain partial JSON or multiple objects,
                                # try the aggregate so far.
                                try:
                                    aggregate = "\n".join(collected_lines)
                                    candidate = self._safe_parse_json(aggregate)
                                    last_parsed = candidate
                                except Exception:
                                    candidate = None

                            # If we have a parsed event, stitch together any `response` pieces.
                            if isinstance(candidate, dict) and "response" in candidate:
                                # Some responses include leading spaces; preserve exact concatenation
                                aggregated_response += str(candidate.get("response", ""))

                            # If model signals completion, attempt to parse the aggregated response
                            if isinstance(candidate, dict) and candidate.get("done") is True:
                                # Try parsing the aggregated response as JSON
                                try:
                                    parsed = self._safe_parse_json(aggregated_response)
                                    return parsed
                                except Exception:
                                    # If parsing fails, return a structured object with raw text
                                    return {"raw_response": aggregated_response, **(candidate or {})}

                        # Stream ended: try to parse aggregated_response first, then fall back
                        if aggregated_response:
                            try:
                                parsed = self._safe_parse_json(aggregated_response)
                                return parsed
                            except Exception:
                                # If parsing fails, but we have a last_parsed dict, return it
                                if last_parsed is not None:
                                    return {"raw_response": aggregated_response, **last_parsed}
                                # Otherwise, return the raw text
                                return {"raw_response": aggregated_response}

                        # If no aggregated response, prefer last parsed object
                        if last_parsed is not None:
                            return last_parsed

                        # As a final attempt, try parsing the full collected lines
                        full_text = "\n".join(collected_lines)
                        if full_text:
                            parsed = self._safe_parse_json(full_text)
                            return parsed

                        # Nothing parsed; raise to trigger retry logic
                        raise RuntimeError("Empty response from Ollama stream")
            except Exception as exc:  # noqa: BLE001 - handle transport/parsing errors
                last_exc = exc
                logger.warning("Ollama request failed (attempt %d/%d): %s", attempt, self.retries, exc)
                if attempt < self.retries:
                    await asyncio.sleep(self.retry_delay_ms / 1000.0)

        logger.error("All Ollama attempts failed after %d tries", self.retries)
        raise RuntimeError("Ollama inference failed") from last_exc


__all__ = ["OllamaClient"]
