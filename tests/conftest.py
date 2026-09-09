import os
import subprocess
import time
from pathlib import Path

import pytest

from compact_mcp.client import Client

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def blender(tmp_path_factory):
    exe = os.environ.get("BLENDER_EXE")
    if not exe:
        pytest.skip("Set BLENDER_EXE to run real Blender integration tests")
    folder = tmp_path_factory.mktemp("blender")
    descriptor = folder / "connection.json"
    stop = folder / "stop"
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    # Export files unique to this run; copied to stable artifacts only after verification.
    log_path = artifacts / "blender-test.log"
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            [
                exe,
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(ROOT / "scripts/blender_host.py"),
                "--",
                "--connection",
                str(descriptor),
                "--output",
                str(folder / "exports"),
                "--stop",
                str(stop),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 45
            while not descriptor.exists():
                if proc.poll() is not None or time.monotonic() > deadline:
                    pytest.fail(f"Blender did not start. See {log_path}")
                time.sleep(0.2)
            client = Client(descriptor)
            client.call("inspect")
            yield client
        finally:
            stop.touch()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=10)
