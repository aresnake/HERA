# Claude Modeling Guide (HERA + Blender)

This guide summarizes the HERA Blender tools and a recommended batch-first workflow
for safe, headless modeling.

Tools

Inspect
- hera.blender.version
- hera.blender.scene.list_objects
- hera.blender.object.exists
- hera.blender.object.get_location
- hera.blender.object.get_transform
- hera.blender.scene.get_active_object

Modeling
- hera.blender.mesh.create_cube
- hera.blender.mesh.create_uv_sphere
- hera.blender.mesh.create_cylinder
- hera.blender.object.rename
- hera.blender.object.delete
- hera.blender.object.set_transform
- hera.blender.object.move

Batch
- hera.blender.batch (run multiple steps as one call)

Rules
- Always use hera.blender.batch for multi-step plans.
- Always verify with exists/get_location/get_transform after create or transform.
- Never rely on active object or selection; use explicit names.
- Prefer data-API tools and avoid UI or bpy.ops expectations.

Error Handling
- not_found: object name does not exist (rename/get/delete/set/get).
- already_exists: rename target already exists.
- Treat any step with ok=false as a failure; stop unless continue_on_error=true.

Naming Conventions
- Prefix per job/session, e.g. "job123_TableTop".
- Avoid collisions; if a name might exist, call exists first or use a unique prefix.

Example Batch Payloads

1) Create cube + set transform + get transform
```json
{
  "steps": [
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobA_Cube", "size": 2.0, "location": [0,0,0]}},
    {"tool": "hera.blender.object.set_transform", "args": {"name": "JobA_Cube", "location": [1,2,3]}},
    {"tool": "hera.blender.object.get_transform", "args": {"name": "JobA_Cube"}}
  ]
}
```

2) Create UV sphere + rename + delete
```json
{
  "steps": [
    {"tool": "hera.blender.mesh.create_uv_sphere", "args": {"name": "JobB_Sphere", "radius": 1.0, "segments": 24, "rings": 12}},
    {"tool": "hera.blender.object.rename", "args": {"from": "JobB_Sphere", "to": "JobB_SphereFinal"}},
    {"tool": "hera.blender.object.delete", "args": {"name": "JobB_SphereFinal"}}
  ]
}
```

3) Build a simple table (top + 4 legs)
```json
{
  "steps": [
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobC_Top", "size": 2.0, "location": [0,0,1.0]}},
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobC_Leg_FL", "size": 0.3, "location": [0.7,0.7,0.3]}},
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobC_Leg_FR", "size": 0.3, "location": [0.7,-0.7,0.3]}},
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobC_Leg_BL", "size": 0.3, "location": [-0.7,0.7,0.3]}},
    {"tool": "hera.blender.mesh.create_cube", "args": {"name": "JobC_Leg_BR", "size": 0.3, "location": [-0.7,-0.7,0.3]}},
    {"tool": "hera.blender.object.get_transform", "args": {"name": "JobC_Top"}}
  ]
}
```
