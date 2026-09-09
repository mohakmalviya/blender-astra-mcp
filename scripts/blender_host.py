"""Isolated integration-test host. Run ONLY with Blender --background --factory-startup.

The production add-on uses bpy.app.timers; background tests explicitly pump the same poll method.
"""

import argparse
import sys
import time
from pathlib import Path

import bpy

parser = argparse.ArgumentParser()
parser.add_argument("--connection", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--stop", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon"))
import compact_blender  # noqa: E402
from compact_blender.engine import Engine  # noqa: E402
from compact_blender.transport import Server  # noqa: E402

# This is a factory startup file in a separate process, never the user's scene.
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(location=(1000, 1000, 1000))
bpy.context.object.name = "UnmanagedSentinel"
compact_blender.register()
server = compact_blender.start(
    args.output, args.connection, ("write", "render", "save", "delete"), timer=False
)
readonly = Server(
    Engine(Path(args.output) / "readonly", ()), Path(args.connection).with_name("readonly.json")
)
try:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline and not Path(args.stop).exists():
        server.poll()
        readonly.poll()
        time.sleep(0.005)
finally:
    readonly.close()
    compact_blender.unregister()
