import json
from pathlib import Path

import pytest

from compact_mcp.client import Client


def descriptor(tmp_path, **changes):
    path = tmp_path / "connection.json"
    path.write_text(
        json.dumps(
            {
                "protocol": 1,
                "host": "127.0.0.1",
                "port": 1,
                "output_dir": str(tmp_path / "exports"),
                "token": "fake",
                **changes,
            }
        )
    )
    return path


def test_remote_endpoint_refused(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        Client(descriptor(tmp_path, host="example.com"))


def test_capture_path_traversal_refused(tmp_path):
    client = Client(descriptor(tmp_path))
    with pytest.raises(ValueError):
        client.image_path("../private.png")
    assert client.image_path("preview.png") == Path(tmp_path / "exports/preview.png")


def test_dead_server_does_not_silently_retry(tmp_path):
    client = Client(descriptor(tmp_path))
    with pytest.raises(RuntimeError, match="outcome may be unknown"):
        client.call("execute", timeout=0.1)
