import socket

import pytest

from contx.web.app import find_open_port


def _occupy(host: str, port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    s.bind((host, port))
    s.listen(1)
    return s


def test_find_open_port_returns_start_when_free():
    # Pick a port likely to be free
    port = find_open_port(54000)
    assert 54000 <= port < 54010


def test_find_open_port_skips_occupied():
    held = _occupy("127.0.0.1", 54200)
    try:
        port = find_open_port(54200)
        assert port != 54200
        assert 54201 <= port < 54210
    finally:
        held.close()


def test_find_open_port_exhausted_raises():
    holders = [_occupy("127.0.0.1", p) for p in range(54300, 54303)]
    try:
        with pytest.raises(OSError):
            find_open_port(54300, attempts=3)
    finally:
        for s in holders:
            s.close()
