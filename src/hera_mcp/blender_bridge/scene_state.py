"""
Compact scene state snapshot utilities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from hera_mcp.core import envelope


def _lazy_bpy():
    import importlib

    try:
        return importlib.import_module("bpy")
    except Exception:
        return None


def _active_scene(bpy_module) -> Any:
    if bpy_module.data.scenes:
        return bpy_module.data.scenes[0]
    return bpy_module.context.scene


def compact_object(obj) -> Dict[str, Any]:
    loc = tuple(getattr(obj, "location", (0.0, 0.0, 0.0)))
    return {
        "name": getattr(obj, "name", "object"),
        "type": getattr(obj, "type", "MESH"),
        "location": [float(loc[0]), float(loc[1]), float(loc[2])],
    }


def snapshot(
    *,
    bpy_module=None,
    offset: int = 0,
    limit: int = envelope.DEFAULT_CHUNK_SIZE,
) -> Dict[str, Any]:
    bpy_module = bpy_module or _lazy_bpy()
    if bpy_module is None:
        state = {"objects": [], "metadata": {"scene": "none", "count": 0}}
        return {"scene_state": state, "resume_token": None, "next_actions": None}
    scene = _active_scene(bpy_module)
    objects = list(scene.objects) if scene else []
    chunk, resume_token = envelope.chunk_list(objects, chunk_size=limit, offset=offset)
    object_payload: List[Dict[str, Any]] = [compact_object(obj) for obj in chunk]
    metadata = {
        "scene": getattr(scene, "name", "Scene"),
        "count": len(objects),
    }
    state = {"objects": object_payload, "metadata": metadata}
    return {
        "scene_state": state,
        "resume_token": resume_token,
        "next_actions": _next_actions(resume_token),
    }


def _next_actions(resume_token: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    if not resume_token:
        return None
    offset = resume_token.get("offset")
    total = resume_token.get("total")
    return [
        f"call scene.snapshot with resume_token.offset={offset} to continue ({offset}/{total})"
    ]
