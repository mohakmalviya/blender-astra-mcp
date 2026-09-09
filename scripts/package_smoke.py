"""Install the built ZIP into an isolated Blender scripts directory and start/stop it."""

import importlib
import sys
from pathlib import Path

import addon_utils
import bpy

zip_path, scratch = sys.argv[sys.argv.index("--") + 1 :]
result = bpy.ops.preferences.addon_install(filepath=zip_path)
assert result == {"FINISHED"}, result
addon_utils.enable("compact_blender", default_set=False)
module = importlib.import_module("compact_blender")
assert module.bl_info["version"] == (0, 2, 0)
server = module.start(Path(scratch) / "exports", Path(scratch) / "connection.json")
callback = module._timer
assert bpy.app.timers.is_registered(callback)
assert server.engine.inspect()["blender"] == bpy.app.version_string
module.stop()
assert not bpy.app.timers.is_registered(callback)
assert not server.descriptor.exists()
addon_utils.disable("compact_blender", default_set=False)
print("PACKAGE_SMOKE_OK")
