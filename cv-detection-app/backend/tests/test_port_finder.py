import socket
import tempfile
import os

from backend.utils.port_finder import find_available_port


def test_find_available_port_pref_free():
    # choose an ephemeral preferred port (0 lets OS pick free port) - function expects int, so use 0
    # find_available_port should accept 0 and return a valid port
    port = find_available_port(0, "8000,8005", port_binding_path=os.path.join(tempfile.gettempdir(), ".port_binding_test"))
    assert isinstance(port, int)
    assert port >= 0


def test_find_available_port_pref_in_use():
    # bind to a port to simulate in-use
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    used_port = s.getsockname()[1]

    # pick fallback range that includes a different port
    fallback_start = used_port + 1
    fallback_end = used_port + 3
    port = find_available_port(used_port, f"{fallback_start},{fallback_end}", port_binding_path=os.path.join(tempfile.gettempdir(), ".port_binding_test2"))
    assert port != used_port
    s.close()
