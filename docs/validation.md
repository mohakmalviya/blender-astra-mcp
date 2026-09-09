# Validation — 2026-09-10

Local environment: Windows 11, Blender **5.1.1**, Python **3.12.10**, MCP Python SDK **1.30.0**.

Executed, not inferred:

- `uv run ruff check --config pyproject.toml .` — passed.
- Full pytest suite with `BLENDER_EXE` and `BLENDER_TEST_UI=1` — **24 passed**, no skips;
  subsequently added isolated ZIP-install smoke test — **1 passed** (25 tests verified in total).
- Add-on ZIP packaging and Python wheel/sdist build — passed.
- Actual ZIP installation into an isolated Blender scripts directory, enable, timer registration,
  start/stop, descriptor removal and disable — passed.
- Separate real Blender background process: registration, scene inspection, operation discovery,
  syntax prevalidation, dry run, partial failure reporting, authenticated request replay,
  linked-copy material isolation, deletion confirmation, path validation, read-only enforcement,
  refusal to edit unmanaged data, a 50-object camera render and `.blend` copy save.
- Official MCP SDK client over actual stdio: initialization, exactly four tools, discovery,
  execution, inspection and PNG image result, all forwarded to real Blender.
- Separate hidden interactive Blender process: actual timer-driven socket execution, Undo of a
  transform batch, timer removal and descriptor cleanup.
- Protocol tests: authentication before dispatch, malformed JSON, request size cap, replay conflict,
  bounded replay cache, loopback restriction and transport failure reporting.

## Payload microbenchmark

[Raw measured result](benchmark.json). The test runs the same 50 transforms individually and batched,
resets object positions between variants, and compares resulting object properties for equality.
Both variants use this project's own bridge, not a fabricated competing-server baseline.

| Metric | Individual | Batched |
|---|---:|---:|
| Calls | 50 | 1 |
| Argument tokens | 1,149 | 1,002 |
| Result tokens | 800 | 16 |
| Total payload tokens | 1,949 | 1,018 |

Tokenizer: `cl100k_base`. **47.77% payload reduction**. Tokens are counted over compact serialized
arguments/results, excluding transport authentication and IDs that are not model-visible.
It also excludes model reasoning, history, system prompts, caching/billing, protocol tool-call
envelopes, images, setup and discovery. No model was invoked or charged by this benchmark.

This does not establish the total token cost or output quality of an autonomous modeling task.
A future comparison should run repeated matched briefs on the same model/settings, collect the
provider's actual usage counters, and score scene/render correctness before comparing consumption.
There is currently no measured comparison against ahujasid/blender-mcp or another product.

## Visual artifact

The example image is a real Cycles render of 50 managed cubes created by five local array operations,
with a managed floor, camera and lights. It demonstrates scene construction and rendering, not
artistic quality, topology quality for production assets, or complex modeling capability.

The editable scene and installable ZIP are provided as release assets. The test scripts recreate
them without touching a user scene. `artifacts/` is ignored because logs can contain local paths.

## Limits of verification

- Blender 4.2+, macOS and Linux behavior are not yet runtime-tested locally.
- CI runs Python checks and package builds; Blender-dependent tests explicitly skip unless a Blender
  executable is supplied. CI passing is not a substitute for the real local Blender tests above.
- This is not a complete security audit, performance stress test, or long-session reliability test.
- Background mode has no Undo guarantee; files and partial writes are not transactional.
