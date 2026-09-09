"""Controlled payload comparison, NOT an end-to-end LLM or competing-product benchmark."""

import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]


def test_measured_batch_payloads(blender):
    enc = tiktoken.get_encoding("cl100k_base")

    def tokens(value):
        return len(enc.encode(json.dumps(value, separators=(",", ":"))))

    setup = [
        {"op": "primitive", "kind": "cube", "name": "BenchSeed"},
        {"op": "array", "name": "BenchSeed", "count": 49, "offset": [1, 0, 0], "prefix": "Bench"},
    ]
    assert blender.call("execute", {"steps": setup})["ok"]
    names = ["BenchSeed"] + [f"Bench_{i:03d}" for i in range(1, 50)]
    steps = [{"op": "transform", "name": n, "location": [i, 3, 1]} for i, n in enumerate(names)]
    input_single = output_single = 0
    for step in steps:
        params = {"steps": [step]}
        result = blender.call("execute", params)
        assert result["ok"]
        input_single += tokens(params)
        output_single += tokens(result)
    first = blender.call("inspect", {"names": names, "limit": 100})
    # Reset to different positions, then repeat the identical target operations as one batch.
    assert blender.call(
        "execute", {"steps": [{"op": "transform", "name": n, "location": [0, 0, 0]} for n in names]}
    )["ok"]
    params = {"steps": steps}
    result = blender.call("execute", params)
    assert result["ok"]
    second = blender.call("inspect", {"names": names, "limit": 100})
    assert first == second
    report = {
        "method": "Same 50 transforms, same bridge and Blender state, 50 calls versus one batch",
        "tokenizer": "cl100k_base",
        "blender": first["blender"],
        "equivalent_final_state": True,
        "individual": {"calls": 50, "input_tokens": input_single, "output_tokens": output_single},
        "batched": {"calls": 1, "input_tokens": tokens(params), "output_tokens": tokens(result)},
        "excluded": [
            "model reasoning",
            "system and conversation context",
            "cached token billing",
            "tool-call envelopes",
            "image tokens",
            "initial setup",
            "discovery",
        ],
        "limitation": "Protocol payload microbenchmark; not measured savings against another MCP or an LLM session",
    }
    baseline = input_single + output_single
    batched = tokens(params) + tokens(result)
    report["payload_reduction_percent"] = round((1 - batched / baseline) * 100, 2)
    (ROOT / "artifacts/benchmark.json").write_text(json.dumps(report, indent=2))
    assert batched < baseline
    # Clean benchmark objects explicitly through the tested permission boundary.
    assert blender.call("execute", {"steps": [{"op": "delete", "names": names, "confirm": True}]})["ok"]
