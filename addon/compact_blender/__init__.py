"""Install this directory as a legacy Blender add-on (ZIP provided by package script)."""

import bpy
from bpy.app.handlers import persistent

from .engine import Engine
from .transport import Server, state_dir

bl_info = {
    "name": "Compact Blender MCP",
    "author": "Mohak Malviya",
    "version": (0, 2, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Compact MCP",
    "description": "Batched Blender operations through four compact MCP tools",
    "category": "Interface",
}

_server = None
_timer = None


def stop():
    global _server, _timer
    if _server is not None:
        if _timer is not None and bpy.app.timers.is_registered(_timer):
            bpy.app.timers.unregister(_timer)
        _server.close()
        _server = None
        _timer = None


def start(output_dir=None, descriptor=None, permissions=("write", "render"), timer=True):
    global _server, _timer
    if _server is not None:
        raise RuntimeError("Compact MCP already running")
    _server = Server(Engine(output_dir or state_dir() / "exports", permissions), descriptor)
    if timer:
        _timer = _server.poll
        bpy.app.timers.register(_timer, first_interval=0.1)
    return _server


@persistent
def on_load(_):
    # A new file is a new authority boundary. User must start again explicitly.
    stop()


class COMPACT_OT_start(bpy.types.Operator):
    bl_idname = "compact_mcp.start"
    bl_label = "Start bridge"

    def execute(self, context):
        settings = context.scene
        permissions = [
            key for key in ("write", "render", "delete", "save", "python") if getattr(settings, f"compact_allow_{key}")
        ]
        start(permissions=permissions)
        self.report({"INFO"}, "Bridge started on loopback. Permissions fixed until stopped.")
        return {"FINISHED"}


class COMPACT_OT_stop(bpy.types.Operator):
    bl_idname = "compact_mcp.stop"
    bl_label = "Stop bridge"

    def execute(self, context):
        stop()
        return {"FINISHED"}


class COMPACT_PT_panel(bpy.types.Panel):
    bl_label = "Compact MCP"
    bl_idname = "COMPACT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Compact MCP"

    def draw(self, context):
        layout = self.layout
        if _server:
            layout.label(text="Connected locally; active scene access")
            layout.label(text="Enabled: " + ", ".join(sorted(_server.engine.permissions)))
            layout.operator("compact_mcp.stop")
        else:
            for key in ("write", "render", "delete", "save", "python"):
                layout.prop(context.scene, f"compact_allow_{key}")
            layout.label(text="Python grants unrestricted local code access")
            layout.operator("compact_mcp.start")


CLASSES = (COMPACT_OT_start, COMPACT_OT_stop, COMPACT_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    for key in ("write", "render", "delete", "save", "python"):
        setattr(
            bpy.types.Scene,
            f"compact_allow_{key}",
            bpy.props.BoolProperty(name=f"Allow {key}", default=key in ("write", "render")),
        )
    bpy.app.handlers.load_pre.append(on_load)


def unregister():
    stop()
    if on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(on_load)
    for key in ("write", "render", "delete", "save", "python"):
        delattr(bpy.types.Scene, f"compact_allow_{key}")
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
