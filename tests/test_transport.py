"""Transport tests do not import Blender or start an external service."""

import importlib.util
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "compact_transport", ROOT / "addon/compact_blender/transport.py"
)
transport = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = transport
spec.loader.exec_module(transport)


class FakeEngine:
    def __init__(self, root):
        self.output_dir = root
        self.calls = 0

    def dispatch(self, method, params):
        self.calls += 1
        return {"method": method, "calls": self.calls}


@pytest.fixture
def server(tmp_path):
    instance = transport.Server(FakeEngine(tmp_path / "exports"), tmp_path / "connection.json")
    yield instance
    instance.close()


def request(server, **changes):
    return {"id": "a", "token": server.token, "method": "execute", "params": {}, **changes}


def test_authorization_precedes_execution(server):
    assert server.handle(request(server, token="wrong"))["error"] == "Unauthorized"
    assert server.engine.calls == 0


def test_replay_does_not_duplicate_execution(server):
    first = server.handle(request(server))
    assert server.handle(request(server)) == first
    assert server.engine.calls == 1


def test_reused_id_cannot_change_operation(server):
    server.handle(request(server))
    assert not server.handle(request(server, params={"different": True}))["ok"]
    assert server.engine.calls == 1


def test_descriptor_lifecycle_and_loopback(server):
    assert server.socket.getsockname()[0] == "127.0.0.1"
    assert server.descriptor.exists()
    server.close()
    assert not server.descriptor.exists()


def test_network_invalid_json_is_rejected(server):
    with socket.create_connection(server.socket.getsockname()) as client:
        client.sendall(b"not JSON\n")
        server.poll()
        client.settimeout(1)
        assert b"Invalid JSON" in client.recv(4096)
    assert server.engine.calls == 0


def test_request_size_limit(server):
    with socket.create_connection(server.socket.getsockname()) as client:
        client.sendall(b"x" * (transport.MAX_REQUEST + 1))
        for _ in range(10):
            server.poll()
        client.settimeout(1)
        assert b"Request too large" in client.recv(4096)
    assert server.engine.calls == 0


def test_cache_bounded(server):
    for i in range(140):
        server.handle(request(server, id=str(i)))
    assert len(server.cache) == 128


def test_bad_shapes_rejected(server):
    for value in ([], None, "text", 42):
        assert not server.handle(value)["ok"]
    assert not server.handle(request(server, params=[]))["ok"]
    assert not server.handle(request(server, id=""))["ok"]
