"""Exactly four MCP tools. Detailed operation descriptions are fetched on demand."""

import json
import uuid

from mcp.server.fastmcp import FastMCP, Image

from .client import Client

mcp = FastMCP(
    "blender-compact",
    instructions=(
        "Discover an operation before use. Batch related edits. Inspect narrowly; capture only when visual feedback "
        "is needed. Only managed objects may be edited. Partial batch failures persist; inspect before retrying."
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
def execute(steps: list[dict], dry_run: bool = False) -> str:
    """Execute up to 100 {'op': name, ...arguments} steps. Returns counts/errors, not full scene data.

    dry_run checks syntax/permissions only. Runtime failures are partial, not transactional.
    """
    return compact(Client().call("execute", {"steps": steps, "dry_run": dry_run}))


@mcp.tool()
def capture(size: int = 512) -> Image:
    """Render the active camera as a PNG (64..1024 square). Blocks Blender while rendering."""
    client = Client()
    result = client.call("capture", {"filename": f"preview-{uuid.uuid4().hex}.png", "size": size})
    return Image(path=str(client.image_path(result["file"])))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
