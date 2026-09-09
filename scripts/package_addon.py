"""Build an installable Blender add-on ZIP, excluding caches and runtime state."""

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
dist = root / "dist"
dist.mkdir(exist_ok=True)
target = dist / "compact_blender-0.1.0.zip"
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "addon/compact_blender").glob("*.py")):
        archive.write(path, f"compact_blender/{path.name}")
(dist / "SHA256SUMS").write_text(f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {target.name}\n")
print(target)
