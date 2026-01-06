"""
Scene tool: hera.object.get
Inspect an object from bpy.data (data-first).
"""

from __future__ import annotations

from typing import Any, Dict
from time import perf_counter

from hera_mcp.blender_bridge import scene_state


def tool_get_object(name: str) -> Dict[str, Any]:
    t0 = perf_counter()

    # Import bpy only inside Blender
    try:
        import bpy  # type: ignore
    except Exception as exc:
        return {
            "status": "error",
            "operation": "object.get",
            "error": f"bpy unavailable (must run inside Blender): {exc}",
            "scene_state": scene_state.snapshot().get("scene_state", {}),
            "data": {"object": None},
            "metrics": {"duration_ms": int((perf_counter() - t0) * 1000)},
        }

    obj = bpy.data.objects.get(name)
    if obj is None:
        return {
            "status": "error",
            "operation": "object.get",
            "error": f"Object not found: {name}",
            "scene_state": scene_state.snapshot().get("scene_state", {}),
            "data": {"object": None},
            "metrics": {"duration_ms": int((perf_counter() - t0) * 1000)},
        }

    data = {
        "name": obj.name,
        "type": obj.type,
        "location": [float(obj.location.x), float(obj.location.y), float(obj.location.z)],
        "rotation_euler": [float(obj.rotation_euler.x), float(obj.rotation_euler.y), float(obj.rotation_euler.z)],
        "scale": [float(obj.scale.x), float(obj.scale.y), float(obj.scale.z)],
    }

    return {
        "status": "success",
        "operation": "object.get",
        "scene_state": scene_state.snapshot().get("scene_state", {}),
        "data": {"object": data},
        "metrics": {"duration_ms": int((perf_counter() - t0) * 1000)},
    }
