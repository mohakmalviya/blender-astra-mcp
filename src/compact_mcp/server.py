"""Exactly four MCP tools. Detailed operation descriptions are fetched on demand."""

import json
import uuid

from mcp.server.fastmcp import FastMCP, Image

from .client import Client

mcp = FastMCP(
    "blender-compact",
    instructions=(
        "Discover an operation before use. Batch related edits. Inspect narrowly; capture only when visual feedback "
        "is needed. Existing scenes are editable. Discover python for full bpy access (must be enabled in Blender). Partial batch failures persist; inspect before retrying."
    ),
)


def compact(result):
    return json.dumps(result, separators=(",", ":"), allow_nan=False)


@mcp.tool()
def inspect(names: list[str] | None = None, limit: int = 20, offset: int = 0) -> str:
    """Read a bounded scene summary; pass names for detailed object properties."""
    return compact(Client().call("inspect", {"names": names, "limit": limit, "offset": offset}))


@mcp.tool()
def discover(operation: str | None = None) -> str:
    """List operation summaries, or fetch one operation's arguments."""
    return compact(Client().call("discover", {"operation": operation}))


@mcp.tool()
def execute(steps: list[dict], dry_run: bool = False, timeout: int = 180) -> str:
    """Execute up to 100 {'op': name, ...arguments} steps. Returns counts/errors, not full scene data.

    dry_run checks syntax/permissions only. Runtime failures are partial, not transactional.
    """
    if not 1 <= timeout <= 86400:
        raise ValueError("timeout must be 1..86400 seconds; timeout does not cancel Blender work")
    return compact(Client().call("execute", {"steps": steps, "dry_run": dry_run}, timeout=timeout))


@mcp.tool()
def capture(size: int = 512, view: str = "camera") -> Image:
    """PNG preview (64..1024): camera render or viewport (requires interactive 3D View)."""
    client = Client()
    result = client.call(
        "capture", {"filename": f"preview-{uuid.uuid4().hex}.png", "size": size, "view": view}
    )
    return Image(path=str(client.image_path(result["file"])))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
