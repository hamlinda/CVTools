"""Port negotiation utility for the CV detection app.

Functions:
  - find_available_port(preferred, fallback_range, port_binding_path='.port_binding') -> int
  - get_lan_ip() -> str

Writes the selected port to `.port_binding` and logs the LAN-accessible URL.
"""
import logging
import os
import socket
from typing import Optional


def get_lan_ip() -> str:
    """Return a LAN-accessible IP address for this host, falling back to 127.0.0.1."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable; used to determine local interface
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


def _is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a TCP port is available on the given host.

    Attempts to bind and immediately close the socket. Returns True if bind succeeds.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(preferred: int, fallback_range: str, port_binding_path: str = ".port_binding", host: str = "0.0.0.0") -> int:
    """Select an available port.

    Args:
        preferred: preferred port number to try first.
        fallback_range: string in the form "start,end" (inclusive).
        port_binding_path: path to write the selected port for external processes.
        host: interface to check/bind (default 0.0.0.0).

    Returns:
        The selected port number.

    Raises:
        ValueError: if fallback_range is malformed.
        RuntimeError: if no ports are available.
    """
    logging.info("Trying preferred port %d", preferred)

    if _is_port_free(preferred, host=host):
        selected = preferred
        note = None
    else:
        # parse fallback_range like "8081,8090"
        try:
            start_str, end_str = fallback_range.split(",")
            start = int(start_str.strip())
            end = int(end_str.strip())
        except Exception as e:
            raise ValueError("fallback_range must be 'start,end' (e.g. '8081,8090')") from e

        selected = None
        for p in range(start, end + 1):
            if _is_port_free(p, host=host):
                selected = p
                break

        if selected is None:
            raise RuntimeError(f"No available port in range {start}-{end}")

        note = f"Preferred port {preferred} was in use — bound to {selected} instead."
        logging.warning(note)

    # write the port binding for external scripts to consume
    try:
        with open(port_binding_path, "w") as f:
            f.write(str(selected))
    except Exception:
        logging.exception("Failed to write port binding to %s", port_binding_path)

    lan_ip = get_lan_ip()
    if note:
        logging.info("✅ App running at: http://%s:%d  API docs: http://%s:%d/docs ⚠️ %s", lan_ip, selected, lan_ip, selected, note)
    else:
        logging.info("✅ App running at: http://%s:%d  API docs: http://%s:%d/docs", lan_ip, selected, lan_ip, selected)

    return selected


__all__ = ["find_available_port", "get_lan_ip"]
