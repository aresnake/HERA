"""
Move object tool (translation only).
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core import envelope
from hera_mcp.core.coerce import to_name, to_vector3
from hera_mcp.core.queue import mono_queue
from hera_mcp.core.safe_exec import safe_execute


def _bpy():
    return importlib.import_module("bpy")


def _scene_state_provider() -> Dict[str, Any]:
    return scene_state.snapshot().get("scene_state", {})


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    name = to_name(params.get("name") or params.get("object"))
    delta = to_vector3(params.get("delta"))
    absolute = params.get("location")
    absolute_loc = to_vector3(absolute) if absolute is not None else None

    def _op():
        bpy_module = _bpy()
        obj = bpy_module.data.objects.get(name)
        if obj is None:
            return {
                "status": "error",
                "error": envelope.build_error(
                    "not_found",
                    f"Object not found: {name}",
                    recoverable=False,
                ),
            }
        if absolute_loc is not None:
            obj.location = absolute_loc
        else:
            obj.location = (
                float(obj.location.x) + delta[0],
                float(obj.location.y) + delta[1],
                float(obj.location.z) + delta[2],
            )
        diff = {"created": [], "modified": [obj.name], "deleted": []}
        snap = scene_state.snapshot()
        return {
            "status": "success",
            "data": {"object": {"name": obj.name, "location": list(obj.location)}, "diff": diff},
            "scene_state": {**(snap.get("scene_state") or {}), "ok": True},
            "resume_token": snap.get("resume_token"),
            "next_actions": snap.get("next_actions"),
        }

    return mono_queue.run(lambda: safe_execute("scene.move_object", _op, _scene_state_provider))


def tool_move_object(
    name: str,
    location=None,
    delta=None,
) -> Dict[str, Any]:
    """
    Stable public wrapper for Blender tests.
    """
    params: Dict[str, Any] = {"name": name}
    if location is not None:
        params["location"] = location
    if delta is not None:
        params["delta"] = delta
    return run(params)
