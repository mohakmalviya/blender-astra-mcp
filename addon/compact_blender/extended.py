"""Full Blender API access plus short operations for common repetitive edits.

Python is intentionally unrestricted, explicitly enabled, and always runs on the
Blender main thread. It is not covered by the narrower write/save/delete toggles.
"""

import contextlib
import io
import json

import bpy


OPERATIONS = {
    "python": {
        "summary": "Full bpy/Python API: nodes, rigs, simulation, files, operators; unrestricted local code",
        "args": {
            "code": "Python source; bpy, params, output_dir provided; assign result for JSON return",
            "params": "optional JSON object",
            "max_output": "0..32000 characters, default 2000",
        },
    },
    "modifier": {
        "summary": "Add or update an object's modifier",
        "args": {
            "name": "object name",
            "modifier": "modifier name",
            "type": "Blender modifier enum, required if new",
            "properties": "optional RNA property/value object",
        },
    },
    "keyframes": {
        "summary": "Insert many animation keys on object or object-data properties",
        "args": {
            "name": "object name",
            "data_path": 'RNA path e.g. location or pose.bones["Bone"].rotation_euler',
            "keys": "list of [frame,value] pairs",
            "target": "object|data, default object",
            "index": "optional channel index; default -1 (all channels)",
        },
    },
    "frame": {
        "summary": "Set/evaluate scene frame or animation range",
        "args": {"frame": "optional integer", "start": "optional integer", "end": "optional integer"},
    },
    "properties": {
        "summary": "Set RNA properties on object, its data, scene or render settings",
        "args": {
            "name": "object name for object/data targets",
            "target": "object|data|scene|render; default object",
            "values": 'RNA path/value object, e.g. {"hide_render":true}',
        },
    },
    "rna": {
        "summary": "Discover Blender RNA properties/enums for a type, bounded and filterable",
        "args": {
            "type": "bpy.types identifier e.g. BevelModifier",
            "contains": "optional property-name filter",
            "offset": "default 0",
            "limit": "1..100, default 20",
        },
    },
    "render": {
        "summary": "Render still or animation using current scene settings and resolution; blocking",
        "args": {"filename": "simple output filename/prefix", "animation": "boolean default false"},
    },
}


def validate(op, s):
    if op not in OPERATIONS:
        return False
    required = {
        "python": ("code",),
        "modifier": ("name", "modifier"),
        "keyframes": ("name", "data_path", "keys"),
        "frame": (),
        "properties": ("values",),
        "rna": ("type",),
        "render": ("filename",),
    }
    for key in required[op]:
        if key not in s:
            raise ValueError(f"{op} needs {key}")
    if op == "python":
        if not isinstance(s["code"], str):
            raise ValueError("code must be a string")
        compile(s["code"], "<astra-mcp>", "exec")
        if not isinstance(s.get("params", {}), dict):
            raise ValueError("params must be an object")
        if type(s.get("max_output", 2000)) is not int or not 0 <= s.get("max_output", 2000) <= 32000:
            raise ValueError("max_output must be 0..32000")
    if op in ("modifier", "properties"):
        if not isinstance(s.get("properties" if op == "modifier" else "values", {}), dict):
            raise ValueError("properties/values must be an object")
    if op in ("keyframes", "properties"):
        allowed = ("object", "data") if op == "keyframes" else ("object", "data", "scene", "render")
        if s.get("target", "object") not in allowed:
            raise ValueError(f"target must be one of {allowed}")
        if s.get("target", "object") in ("object", "data") and "name" not in s:
            raise ValueError("object/data targets need name")
    if op == "keyframes":
        keys = s["keys"]
        if not isinstance(keys, list) or not 1 <= len(keys) <= 1000:
            raise ValueError("keys must contain 1..1000 [frame,value] pairs")
        for key in keys:
            if not isinstance(key, list) or len(key) != 2 or type(key[0]) not in (int, float):
                raise ValueError("Each key must be [numeric frame,value]")
        if type(s.get("index", -1)) is not int or s.get("index", -1) < -1:
            raise ValueError("index must be -1 or a nonnegative integer")
    if op == "frame":
        for key in ("frame", "start", "end"):
            if key in s and (type(s[key]) is not int or not -1048574 <= s[key] <= 1048574):
                raise ValueError("frames must be integers within Blender's frame limits")
    if op == "rna":
        if type(s.get("limit", 20)) is not int or not 1 <= s.get("limit", 20) <= 100:
            raise ValueError("limit must be 1..100")
        if type(s.get("offset", 0)) is not int or s.get("offset", 0) < 0:
            raise ValueError("offset must be nonnegative")
    if op == "render" and type(s.get("animation", False)) is not bool:
        raise ValueError("animation must be boolean")
    return True


class BoundedOutput(io.TextIOBase):
    def __init__(self, limit):
        self.limit = limit
        self.text = ""
        self.total = 0

    def write(self, text):
        self.total += len(text)
        self.text += text[: max(0, self.limit - len(self.text))]
        return len(text)


def set_path(target, path, value):
    # RNA resolves collection lookups without evaluating Python expressions.
    parent, _, attribute = path.rpartition(".")
    owner = target.path_resolve(parent) if parent else target
    if not attribute.isidentifier() or attribute.startswith("_"):
        raise ValueError("RNA path must end with a public property name")
    setattr(owner, attribute, value)


def run(engine, s):
    from .engine import owned, output_file

    op = s["op"]
    if op not in OPERATIONS:
        return None
    if op == "python":
        limit = s.get("max_output", 2000)
        capture = BoundedOutput(limit)
        namespace = {"bpy": bpy, "params": s.get("params", {}), "output_dir": str(engine.output_dir)}
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            exec(compile(s["code"], "<astra-mcp>", "exec"), namespace)
        value = namespace.get("result")
        # Reject non-JSON results explicitly, rather than leaking opaque bpy representations.
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        response = {}
        if "result" in namespace:
            if len(encoded) > limit:
                response.update(
                    result_preview=encoded[:limit], result_truncated=True, result_chars=len(encoded)
                )
            else:
                response["value"] = value
        if capture.total:
            response.update(stdout=capture.text, stdout_truncated=capture.total > limit)
        # Python may mutate anything; never invent an object-change count.
        return {"result": response}
    if op == "modifier":
        obj = owned(s["name"])
        mod = obj.modifiers.get(s["modifier"])
        if mod is None:
            if "type" not in s:
                raise ValueError("A new modifier needs type")
            mod = obj.modifiers.new(s["modifier"], s["type"])
        elif "type" in s and mod.type != s["type"]:
            raise ValueError("Existing modifier has a different type")
        for key, value in s.get("properties", {}).items():
            set_path(mod, key, value)
        return {"changed": 1}
    if op in ("properties", "keyframes"):
        kind = s.get("target", "object")
        target = bpy.context.scene if kind in ("scene", "render") else owned(s["name"])
        if kind == "data":
            target = target.data
        elif kind == "render":
            target = target.render
        if op == "properties":
            for key, value in s["values"].items():
                set_path(target, key, value)
        else:
            path = s["data_path"]
            index = s.get("index", -1)
            for frame, value in s["keys"]:
                if index == -1:
                    set_path(target, path, value)
                else:
                    target.path_resolve(path)[index] = value
                if not target.keyframe_insert(data_path=path, frame=frame, index=index):
                    raise RuntimeError("Blender rejected keyframe insertion")
        return {"changed": 1}
    if op == "frame":
        scene = bpy.context.scene
        for key, attr in (("start", "frame_start"), ("end", "frame_end")):
            if key in s:
                setattr(scene, attr, s[key])
        if "frame" in s:
            scene.frame_set(s["frame"])
        return {
            "changed": 0,
            "result": {"frame": scene.frame_current, "start": scene.frame_start, "end": scene.frame_end},
        }
    if op == "rna":
        rna = getattr(bpy.types, s["type"]).bl_rna
        props = [p for p in rna.properties if s.get("contains", "").lower() in p.identifier.lower()]
        offset, limit = s.get("offset", 0), s.get("limit", 20)
        rows = []
        for p in props[offset : offset + limit]:
            row = {"name": p.identifier, "type": p.type, "readonly": p.is_readonly}
            if p.type == "ENUM":
                row["enum"] = [e.identifier for e in p.enum_items]
            rows.append(row)
        return {
            "result": {
                "properties": rows,
                "total": len(props),
                "next_offset": offset + limit if offset + limit < len(props) else None,
            }
        }
    if op == "render":
        filename = s["filename"]
        path = output_file(engine.output_dir, filename, "")
        # One directory per job also prevents animation frame collisions.
        job = path.with_name(path.name + ".render")
        job.mkdir(exist_ok=False)
        scene = bpy.context.scene
        original = scene.render.filepath
        try:
            scene.render.filepath = str(job / filename)
            bpy.ops.render.render(
                write_still=not s.get("animation", False), animation=s.get("animation", False)
            )
            files = [str(p.relative_to(engine.output_dir)) for p in job.iterdir() if p.is_file()]
            if not files:
                raise RuntimeError("Render produced no files")
            return {"result": {"directory": job.name, "files": files[:20], "total": len(files)}}
        finally:
            scene.render.filepath = original
    raise ValueError("Unhandled operation")
