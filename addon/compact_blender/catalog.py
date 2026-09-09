"""Small operation vocabulary; only discovered schemas enter the agent context."""

from .extended import OPERATIONS

CATALOG = {
    "primitive": {
        "summary": "Create a managed mesh",
        "args": {
            "name": "unique string",
            "kind": "cube|sphere|plane|cylinder|cone",
            "location": "[x,y,z], default [0,0,0]",
            "scale": "[x,y,z], default [1,1,1]",
        },
    },
    "transform": {
        "summary": "Transform one managed object",
        "args": {
            "name": "existing managed name",
            "location": "optional [x,y,z]",
            "rotation": "optional Euler radians [x,y,z]",
            "scale": "optional [x,y,z]",
        },
    },
    "material": {
        "summary": "Create/update a managed Principled material",
        "args": {
            "name": "material name",
            "color": "RGBA [0..1]",
            "metallic": "0..1 default 0",
            "roughness": "0..1 default 0.5",
        },
    },
    "assign_material": {
        "summary": "Replace a managed mesh's material slots",
        "args": {"name": "managed mesh name", "material": "managed material name"},
    },
    "array": {
        "summary": "Create linked copies along an offset in ONE operation",
        "args": {
            "name": "managed source",
            "count": "1..200 copies, excludes source",
            "offset": "[x,y,z] step",
            "prefix": "unique copy prefix",
        },
    },
    "light": {
        "summary": "Create managed light",
        "args": {
            "name": "unique name",
            "kind": "AREA|POINT|SUN default AREA",
            "energy": "0..10000",
            "location": "[x,y,z]",
            "target": "optional aim point [x,y,z]",
            "size": "0.01..100",
        },
    },
    "camera": {
        "summary": "Create managed camera and make it active",
        "args": {
            "name": "unique name",
            "location": "[x,y,z]",
            "target": "aim point [x,y,z]",
            "lens": "10..200 mm default 50",
        },
    },
    "delete": {
        "summary": "Delete managed objects only; requires delete permission AND confirm",
        "args": {"names": "list of up to 200 managed names", "confirm": "true"},
    },
    "save": {
        "summary": "Save a copy under the configured output directory; existing files refused",
        "args": {"filename": "basename ending .blend"},
    },
}

CATALOG.update(OPERATIONS)
for entry in CATALOG.values():
    entry["summary"] = entry["summary"].replace("managed ", "")
    entry["args"] = {k: v.replace("managed ", "") for k, v in entry["args"].items()}

PERMISSIONS = {
    name: ("delete" if name == "delete" else "save" if name == "save" else "write") for name in CATALOG
}
PERMISSIONS.update(python="python", render="render", rna=None)


def discover(operation=None):
    if operation is None:
        return {name: entry["summary"] for name, entry in CATALOG.items()}
    if operation not in CATALOG:
        raise ValueError(f"Unknown operation: {operation}")
    return CATALOG[operation]
