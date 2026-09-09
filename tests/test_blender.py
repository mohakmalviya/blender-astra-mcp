import asyncio
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from compact_mcp.client import Client

ROOT = Path(__file__).resolve().parents[1]


def create(blender, name):
    return blender.call("execute", {"steps": [{"op": "primitive", "kind": "cube", "name": name}]})


def test_real_blender_discovery_and_read(blender):
    assert "primitive" in blender.call("discover")
    assert "args" in blender.call("discover", {"operation": "array"})
    assert blender.call("inspect")["blender"]


def test_prevalidation_prevents_earlier_writes(blender):
    with pytest.raises(RuntimeError, match="Unknown operation"):
        blender.call(
            "execute",
            {"steps": [{"op": "primitive", "kind": "cube", "name": "ShouldNotExist"}, {"op": "run_python"}]},
        )
    assert blender.call("inspect", {"names": ["ShouldNotExist"]})["total"] == 0


def test_dry_run_is_explicitly_limited(blender):
    result = blender.call(
        "execute", {"steps": [{"op": "primitive", "kind": "sphere", "name": "Dry"}], "dry_run": True}
    )
    assert result["executed"] == 0
    assert blender.call("inspect", {"names": ["Dry"]})["total"] == 0


def test_runtime_partial_failure_is_reported(blender):
    result = blender.call(
        "execute",
        {
            "steps": [
                {"op": "primitive", "kind": "cube", "name": "Partial"},
                {"op": "transform", "name": "DoesNotExist", "scale": [2, 2, 2]},
            ]
        },
    )
    assert result["ok"] is False and result["completed"] == 1 and result["failed_index"] == 1
    assert blender.call("inspect", {"names": ["Partial"]})["total"] == 1


def test_real_server_replay(blender):
    rid = str(uuid.uuid4())
    params = {"steps": [{"op": "primitive", "kind": "cube", "name": "Replay"}]}
    a = blender.call("execute", params, rid)
    assert blender.call("execute", params, rid) == a
    assert blender.call("inspect", {"names": ["Replay"]})["total"] == 1
    with pytest.raises(RuntimeError, match="reused"):
        blender.call("inspect", {}, rid)


def test_array_material_copy_isolation(blender):
    result = blender.call(
        "execute",
        {
            "steps": [
                {"op": "primitive", "kind": "cube", "name": "ArraySeed"},
                {"op": "material", "name": "Red", "color": [1, 0, 0, 1]},
                {"op": "material", "name": "Blue", "color": [0, 0, 1, 1]},
                {"op": "assign_material", "name": "ArraySeed", "material": "Red"},
                {"op": "array", "name": "ArraySeed", "count": 2, "offset": [2, 0, 0], "prefix": "ArrayCopy"},
                {"op": "assign_material", "name": "ArrayCopy_001", "material": "Blue"},
            ]
        },
    )
    assert result["ok"]
    rows = {
        o["name"]: o
        for o in blender.call("inspect", {"names": ["ArraySeed", "ArrayCopy_001", "ArrayCopy_002"]})[
            "objects"
        ]
    }
    assert rows["ArraySeed"]["materials"] == ["Red"]
    assert rows["ArrayCopy_001"]["materials"] == ["Blue"]
    assert rows["ArrayCopy_002"]["location"] == [4, 0, 0]


def test_delete_confirmation_and_path_validation(blender):
    create(blender, "DeleteMe")
    with pytest.raises(RuntimeError, match="confirm"):
        blender.call("execute", {"steps": [{"op": "delete", "names": ["DeleteMe"], "confirm": False}]})
    assert blender.call("execute", {"steps": [{"op": "delete", "names": ["DeleteMe"], "confirm": True}]})[
        "ok"
    ]
    result = blender.call("execute", {"steps": [{"op": "save", "filename": "../outside.blend"}]})
    assert result["ok"] is False


def test_unmanaged_objects_cannot_be_changed(blender):
    result = blender.call(
        "execute", {"steps": [{"op": "transform", "name": "UnmanagedSentinel", "location": [0, 0, 0]}]}
    )
    assert result["ok"] is False
    assert blender.call("inspect", {"names": ["UnmanagedSentinel"]})["objects"][0]["location"] == [
        1000,
        1000,
        1000,
    ]


def test_readonly_connection_enforces_permissions(blender):
    readonly = Client(Path(blender.info["output_dir"]).parent / "readonly.json")
    assert readonly.call("inspect")["permissions"] == []
    with pytest.raises(RuntimeError, match="Disabled permission: write"):
        create(readonly, "Denied")
    with pytest.raises(RuntimeError, match="Disabled permission: render"):
        readonly.call("capture")


def test_mcp_stdio_roundtrip(blender, monkeypatch):
    # Real SDK client -> subprocess MCP bridge -> local socket -> actual Blender.
    connection = Path(blender.info["output_dir"]).parent / "connection.json"
    monkeypatch.setenv("BLENDER_COMPACT_CONNECTION", str(connection))

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "compact_mcp.server"], env=dict(os.environ)
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {"inspect", "discover", "execute", "capture"}
                result = await session.call_tool("discover", {"operation": "primitive"})
                assert not result.isError
                assert "kind" in result.content[0].text
                result = await session.call_tool(
                    "execute", {"steps": [{"op": "primitive", "kind": "cube", "name": "FromMCP"}]}
                )
                assert not result.isError
                assert json.loads(result.content[0].text)["ok"]
                result = await session.call_tool(
                    "execute",
                    {
                        "steps": [
                            {
                                "op": "camera",
                                "name": "MCPTestCamera",
                                "location": [8, -8, 8],
                                "target": [0, 0, 0],
                            }
                        ]
                    },
                )
                assert not result.isError
                result = await session.call_tool("inspect", {"names": ["FromMCP"]})
                assert not result.isError and json.loads(result.content[0].text)["total"] == 1
                result = await session.call_tool("capture", {"size": 64})
                assert not result.isError
                assert result.content[0].type == "image" and result.content[0].mimeType == "image/png"
                # Keep the exact advertised tool schemas for the reproducible overhead report.
                (ROOT / "artifacts/tool-schemas.json").write_text(
                    json.dumps([t.model_dump(exclude_none=True) for t in tools.tools], indent=2)
                )

    asyncio.run(run())


def test_demo_render_and_save(blender):
    # Move prior test objects away, without deleting anything not created by these tests.
    rows = [o for o in blender.call("inspect", {"limit": 100})["objects"] if o["managed"]]
    if rows:
        result = blender.call(
            "execute",
            {
                "steps": [
                    {"op": "transform", "name": row["name"], "location": [1000, 1000, 1000]} for row in rows
                ]
            },
        )
        assert result["ok"]
    steps = [
        {"op": "material", "name": "Teal", "color": [0.03, 0.5, 0.38, 1], "metallic": 0.3, "roughness": 0.25},
        {"op": "material", "name": "GroundMat", "color": [0.08, 0.1, 0.14, 1], "roughness": 0.8},
    ]
    for row in range(5):
        steps.extend(
            [
                {
                    "op": "primitive",
                    "kind": "cube",
                    "name": f"Tile{row}",
                    "location": [-5.4, (row - 2) * 1.2, 0.4 + row * 0.1],
                    "scale": [0.45, 0.45, 0.4 + row * 0.1],
                },
                {"op": "assign_material", "name": f"Tile{row}", "material": "Teal"},
                {
                    "op": "array",
                    "name": f"Tile{row}",
                    "count": 9,
                    "offset": [1.2, 0, 0],
                    "prefix": f"Row{row}",
                },
            ]
        )
    steps.extend(
        [
            {"op": "primitive", "kind": "plane", "name": "Ground", "scale": [200, 200, 1]},
            {"op": "assign_material", "name": "Ground", "material": "GroundMat"},
            {
                "op": "camera",
                "name": "DemoCamera",
                "location": [12, -15, 13],
                "target": [0, 0, 0.5],
                "lens": 48,
            },
            {
                "op": "light",
                "name": "Key",
                "location": [0, -5, 10],
                "target": [0, 0, 0],
                "energy": 2000,
                "size": 8,
            },
            {
                "op": "light",
                "name": "Rim",
                "location": [0, 6, 8],
                "target": [0, 0, 0],
                "energy": 2500,
                "size": 6,
            },
        ]
    )
    assert blender.call("execute", {"steps": steps})["ok"]
    image = blender.call("capture", {"filename": "demo.png", "size": 768})
    path = blender.image_path(image["file"])
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert image["bytes"] > 10000
    save = blender.call("execute", {"steps": [{"op": "save", "filename": "demo.blend"}]})
    assert save["ok"]
    out = Path(blender.info["output_dir"])
    assert (out / "demo.blend").stat().st_size > 10000
    shutil.copy2(path, ROOT / "artifacts/demo.png")
    shutil.copy2(out / "demo.blend", ROOT / "artifacts/demo.blend")
    (ROOT / "artifacts/demo-steps.json").write_text(json.dumps(steps, indent=2))
