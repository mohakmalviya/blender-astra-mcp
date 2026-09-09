import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from compact_mcp.client import Client

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    not os.environ.get("BLENDER_TEST_UI"), reason="Opt-in real Blender UI timer and undo test"
)
def test_real_timer_and_undo(tmp_path):
    exe = os.environ["BLENDER_EXE"]
    info = None
    if os.name == "nt":
        info = subprocess.STARTUPINFO()
        info.dwFlags = subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0  # Hidden test helper, never the user's interactive Blender window.
    (ROOT / "artifacts").mkdir(exist_ok=True)
    with (ROOT / "artifacts/blender-ui.log").open("w") as log:
        process = subprocess.Popen(
            [
                exe,
                "--factory-startup",
                "--python",
                str(ROOT / "scripts/blender_ui_host.py"),
                "--",
                str(tmp_path),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            startupinfo=info,
        )
        try:

            def wait_for(path):
                deadline = time.monotonic() + 40
                while not path.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        pytest.fail("UI helper stopped or timed out; see artifacts/blender-ui.log")
                    time.sleep(0.1)

            connection = tmp_path / "connection.json"
            wait_for(connection)
            client = Client(connection)
            assert client.call(
                "execute",
                {"steps": [{"op": "primitive", "name": "UITest", "kind": "cube", "location": [1, 2, 3]}]},
            )["ok"]
            assert client.call(
                "execute", {"steps": [{"op": "transform", "name": "UITest", "location": [7, 8, 9]}]}
            )["ok"]
            (tmp_path / "undo").touch()
            wait_for(tmp_path / "ui-result.json")
            result = json.loads((tmp_path / "ui-result.json").read_text())
            assert result == {
                "poll": True,
                "location": [1, 2, 3],
                "timer_removed": True,
                "descriptor_removed": True,
            }
        finally:
            (tmp_path / "stop").touch()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
