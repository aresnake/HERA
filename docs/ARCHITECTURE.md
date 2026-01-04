# Architecture

## Kernels (A–G)
- **A – Envelope**: Build AI-native envelopes with status, diffs, metrics, and scene snapshots. Module: `core/envelope.py`.
- **B – Coercion**: Tolerant parsing of inputs (vectors, names, numbers) to keep schemas loose. Module: `core/coerce.py`.
- **C – Safe Exec**: Guardrails that catch every exception, measure runtime, and emit structured errors. Module: `core/safe_exec.py`.
- **D – Queue**: Mono-thread execution gate to avoid Blender context conflicts. Module: `core/queue.py`.
- **E – Scene State**: Compact headless snapshots plus chunking/resume helpers. Module: `blender_bridge/scene_state.py`.
- **F – MCP Stdio**: Minimal MCP stdio server for Blender headless sessions. Module: `blender_bridge/mcp_stdio.py`.
- **G – Tools**: Stateless tools for health, scene snapshot, create, and move. Modules under `tools/`.

## Module Map
- `hera_mcp/__main__.py`: entrypoint proxy to MCP stdio server.
- `hera_mcp/core/envelope.py`: envelope builders, chunking helpers, and error scaffolding.
- `hera_mcp/core/coerce.py`: tolerant converters (vectors, numbers, names).
- `hera_mcp/core/safe_exec.py`: safe execution wrapper with metrics and envelope assembly.
- `hera_mcp/core/queue.py`: single-thread task gate.
- `hera_mcp/blender_bridge/scene_state.py`: scene snapshot and chunk helpers.
- `hera_mcp/blender_bridge/mcp_stdio.py`: stdio loop to dispatch tools in Blender.
- `hera_mcp/tools/core/health.py`: healthcheck tool.
- `hera_mcp/tools/scene/snapshot.py`: scene snapshot tool (chunked).
- `hera_mcp/tools/scene/create_object.py`: data-first object creation (cube/sphere/camera/light).
- `hera_mcp/tools/scene/move_object.py`: object translation tool.

## Flow
1) Incoming MCP call hits `mcp_stdio` (F) which dispatches through the mono-thread queue (D).
2) Each tool runs inside `safe_execute` (C) to guarantee error envelopes and timing.
3) Tools rely on coercion helpers (B) for tolerant inputs and on data-first Blender APIs.
4) `scene_state` (E) snapshots the scene for every response and handles chunking/resume.
5) `envelope` (A) assembles the final AI-native payload returned to the MCP client.
