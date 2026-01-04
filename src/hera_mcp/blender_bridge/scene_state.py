"""
Compact scene state snapshot utilities.
"""

from __future__ import annotations

import base64
import json
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
    total = len(objects)
    metadata = {
        "scene": getattr(scene, "name", "Scene"),
        "count": total,
    }
    state = {"objects": object_payload, "metadata": metadata}
    next_offset = offset + len(chunk)
    token = _encode_token(next_offset, limit, total) if total > 0 and next_offset < total else None
    return {
        "scene_state": state,
        "resume_token": resume_token,
        "next_actions": _next_actions(resume_token),
        "chunk_token": token,
        "total_objects": total,
        "chunk_size": limit,
    }


def _next_actions(resume_token: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    if not resume_token:
        return None
    offset = resume_token.get("offset")
    total = resume_token.get("total")
    return [
        f"call scene.snapshot with resume_token.offset={offset} to continue ({offset}/{total})"
    ]


def _encode_token(offset: int, limit: int, total: int) -> str:
    payload = {"offset": offset, "limit": limit, "total": total}
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_token(token: str) -> Dict[str, int]:
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
        return {
            "offset": int(data.get("offset", 0)),
            "limit": int(data.get("limit", envelope.DEFAULT_CHUNK_SIZE)),
            "total": int(data.get("total", 0)),
        }
    except Exception:
        return {"offset": 0, "limit": envelope.DEFAULT_CHUNK_SIZE, "total": 0}
