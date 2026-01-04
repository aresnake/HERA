# Tooling Policy

- **Headless-first**: Assume `blender -b --factory-startup`. No UI contexts; avoid `bpy.context.screen/area/region`.
- **Mono-thread**: All tool calls pass through the single-thread queue to avoid data races.
- **Stateless tools**: No hidden globals; every response carries `scene_state`.
- **No bpy.ops**: Prefer `bpy.data` and `bmesh` for mesh creation. Keep contexts untouched.
- **Timeout guard**: Tools must complete in <25s. If an operation risks exceeding, return `status=partial` with `resume_token`.
- **Payload limit**: Chunk lists >100 items; include `resume_token` and `next_actions`.
- **Schema tolerance**: Avoid strict validation—no `required`, no `additionalProperties=false`.
- **Safe execution**: Wrap every tool with `safe_execute`; never leak uncaught exceptions.
