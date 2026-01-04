# HERA MCP Contract

This contract defines the AI-native envelope every tool returns, the error model, and the chunking/resume discipline. All payloads are designed for MCP clients that favor headless Blender `-b`, single-thread execution, and stateless calls.

## Envelope
- `status`: `ok` | `partial` | `error`.
- `operation`: short string identifying the tool invocation (e.g., `scene.create_object`).
- `data`: compact payload for the operation. Omit fields rather than forcing `null`.
- `data_diff`: optional `{created: [...], modified: [...], deleted: [...]}` describing scene deltas.
- `scene_state`: always present; minimal snapshot with `objects` (chunked) and `metadata`.
- `next_actions`: optional guidance for the client (e.g., request next chunk via `resume_token`).
- `metrics`: optional timings or counts. Include `duration_ms` when available.
- `resume_token`: optional opaque token to continue chunked listings.
- `error`: structured error block (below).

Schemas are tolerant: no `required` fields and no `additionalProperties: false`. Clients must be resilient to omitted fields and extensions.

## Errors
- `code`: stable machine-readable code (e.g., `not_found`, `invalid_input`, `internal_error`).
- `message`: human-friendly string.
- `recoverable`: boolean hint for retry suitability.
- `retry_after`: optional milliseconds the client should wait before retrying.
- `details`: optional lightweight context (never a full trace).

Errors never propagate uncaught exceptions; tools wrap execution with `safe_execute`.

## Chunking & Resume
- Lists over 100 items must be chunked.
- Include the delivered slice in `data`.
- Provide `resume_token` describing the next cursor (commonly `offset`).
- Add `next_actions` with the expected follow-up (e.g., `"call scene.snapshot with resume_token.offset=100"`).
- Tools must finish within 25s; long-running calls return `partial` plus `resume_token` to continue.
