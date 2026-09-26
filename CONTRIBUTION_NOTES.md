fix: default capture to EEVEE so previews are never black

`capture` hard-coded `render.engine = "CYCLES"` at 16 samples. On any
scene without world lighting — a fresh Blender file, a freshly loaded
`.blend`, or a headless/background session — Cycles returns an almost
entirely black frame. The PNG is valid and non-trivial in size, so the
call reports success while the preview is useless for visual checks.

Observed on Blender 5.2.2 LTS: two captures of the same unlit scene
returned byte-identical 74,810-byte PNGs that were 100% black.

Changes:
- `Engine.capture` gains an optional `engine` argument.
- Default is `BLENDER_EEVEE_NEXT` (falling back to `BLENDER_EEVEE` on
  builds without it), resolved against the actual enum rather than
  assumed, so this stays correct across Blender versions.
- Cycles is still used when explicitly requested via `engine="CYCLES"`.
- `samples` is now only touched when Cycles is actually selected, and the
  `finally` block checks `samples is not None`. Previously the restore path
  relied on `"samples" in locals()`, which only worked by accident if an
  exception fired before the assignment.
- The MCP `capture` tool exposes the new `engine` parameter and documents
  when to use Cycles.

`tests/test_blender.py` gains a regression test that captures a scene with
deliberately no world, asserting the frame is not a black buffer, plus a
check that the Cycles override still produces a valid PNG. Verified to fail
on the previous `engine.py` and pass with this change.

Tested on Blender 5.2.2 LTS: 25 passed, 1 skipped; ruff clean.
