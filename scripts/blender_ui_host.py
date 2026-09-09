"""Isolated UI/timer/Undo check. No user scene or preferences are loaded or saved."""

import json
import sys
import time
from pathlib import Path

import bpy

folder = Path(sys.argv[sys.argv.index("--") + 1])
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
import compact_blender  # noqa: E402

compact_blender.register()
compact_blender.start(folder / "exports", folder / "connection.json")
deadline = time.monotonic() + 90


def lifecycle():
    if (folder / "undo").exists():
        (folder / "undo").unlink()
        result = {"poll": bpy.ops.ed.undo.poll()}
        if result["poll"]:
            bpy.ops.ed.undo()
            result["location"] = list(bpy.data.objects["UITest"].location)
        callback = compact_blender._timer
        compact_blender.stop()
        result["timer_removed"] = not bpy.app.timers.is_registered(callback)
        result["descriptor_removed"] = not (folder / "connection.json").exists()
        (folder / "ui-result.json").write_text(json.dumps(result))
    if (folder / "stop").exists() or time.monotonic() > deadline:
        compact_blender.unregister()
        bpy.ops.wm.quit_blender()
        return None
    return 0.1


bpy.app.timers.register(lifecycle, first_interval=0.1)
