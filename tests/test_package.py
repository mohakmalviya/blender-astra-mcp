import os
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("BLENDER_EXE"), reason="Requires real Blender for ZIP installation")
def test_zip_installs_and_starts(tmp_path):
    archive_path = tmp_path / "compact_blender.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        for source in sorted((ROOT / "addon/compact_blender").glob("*.py")):
            archive.write(source, f"compact_blender/{source.name}")
    scripts = tmp_path / "scripts"
    (scripts / "addons").mkdir(parents=True)
    env = {**os.environ, "BLENDER_USER_SCRIPTS": str(scripts)}
    result = subprocess.run(
        [
            os.environ["BLENDER_EXE"],
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "scripts/package_smoke.py"),
            "--",
            str(archive_path),
            str(tmp_path),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PACKAGE_SMOKE_OK" in result.stdout
