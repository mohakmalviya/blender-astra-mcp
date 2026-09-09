# Design

## Token budget

Exactly four advertised tools keep discovery separate from execution. `inspect` defaults to 20 objects,
accepts up to 100, and exposes an offset for pagination. Detailed mesh counts/materials appear only for
named objects. No meshes, vertex arrays, scene-wide node dumps or screenshots are returned implicitly.

`execute` accepts up to 100 operations and caps expansion at 500 units per batch. It returns completed
operation/change counts and output basenames rather than echoing every object. `array` is a reusable
local procedure: the model specifies count and offset once, and Blender does the loop.

The four-tool interface alone does not guarantee lower total tokens. Extra discovery calls may cost more
on tiny tasks; batching and narrowly scoped feedback are the main measurable benefits in this release.

## Authority and state

The Blender-side `Engine` owns permissions; the model cannot change them. It edits only data tagged
`blender_compact_mcp`. Object operations additionally require membership in the active scene. This is
an application convention, not cryptographic ownership. A user can deliberately share managed data
with other scenes; managed material changes can affect every consumer of that material.

The add-on creates a managed collection rather than clearing the scene. Camera creation explicitly
changes the active scene camera. Transform arguments are local coordinates; target points used for
new camera/light aiming are world coordinates because newly created objects are unparented.
Material assignment detaches shared mesh data first, preserving other array instances.

## Protocol and lifecycle

One UTF-8 JSON line per TCP connection, max 256 KiB, bound to `127.0.0.1` on an OS-selected port.
The protocol is private to this bridge; MCP clients use the SDK stdio server, not the socket directly.
The descriptor carries protocol version, PID, port, secret and export root.

Each request includes a random client request ID. The server caches the last 128 authenticated
responses and a digest of their arguments. Replaying one cached ID returns the same result; reusing
it with different arguments fails. This is a bounded session cache, **not durable exactly-once delivery**.
There are no automatic mutation retries. After timeout/disconnect, the caller must inspect the state.
An operation may finish after the client stops waiting. Restarting Blender invalidates the token/cache.

Eight clients maximum, bounded receive work, at most one dispatched command per timer tick. Idle
partial connections expire after ten seconds. No background threads are used. Rendering is synchronous:
the UI and transport wait until it finishes, and Stop cannot preempt an in-progress render. There is
no asynchronous job or cancellation API in this first release.

Closing the bridge unregisters the exact timer callable and deletes its descriptor. Loading a `.blend`
stops the bridge and requires an explicit restart. Auth tokens are never included in tool results.

## Failure and Undo semantics

All step syntax and permissions are validated before a batch starts. Existence checks run per operation
so later steps can reference earlier creations. Runtime failures stop the batch; completed operations
persist and a failed operation can have partial effects. `dry_run` checks only syntax/permissions,
not object existence, Blender context viability or disk access. It is not a transaction simulation.

Interactive Blender receives before/after Undo checkpoints when available. One-step undo of a
transform batch is covered by a real UI test. Not all Blender effects are undoable, and files already
rendered or saved remain on disk. Background mode makes no undo promise. Save copies never overwrite.

## Scope after v0.1

Potential extensions: named JSON recipes with explicit parameters, Geometry Nodes operations, versioned
scene deltas, background render jobs, additional export formats and comparative end-to-end agent tasks.
Any new operation needs bounded output, actual Blender tests, and an explicit permission category.
