"""
Scene snapshot tool.
"""

from __future__ import annotations

from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core.coerce import to_float
from hera_mcp.core.safe_exec import safe_execute


def _scene_state_provider() -> Dict[str, Any]:
    snap = scene_state.snapshot()
    ss = snap.get("scene_state") or {}
    return {**ss, "ok": True}


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    offset = int(to_float(params.get("offset") or params.get("resume_offset") or 0))
    limit = int(to_float(params.get("limit") or 100))

    def _op():
        snap = scene_state.snapshot(offset=offset, limit=limit)
        total_objects = snap.get("total_objects", 0)
        chunk_token = snap.get("chunk_token")
        status = "chunked" if chunk_token else ("partial" if snap.get("resume_token") else "success")
        return {
            "status": status,
            "data": {
                "objects": snap.get("scene_state", {}).get("objects", []),
                "first_chunk": snap.get("scene_state", {}).get("objects", []) if chunk_token else None,
                "metadata": snap.get("scene_state", {}).get("metadata", {}),
                "diff": {"created": [], "modified": [], "deleted": []},
                "next_token": chunk_token,
                "chunk_size": snap.get("chunk_size"),
                "total_objects": total_objects,
            },
            "scene_state": {**(snap.get("scene_state") or {}), "ok": True},
            "resume_token": snap.get("resume_token"),
            "next_actions": snap.get("next_actions"),
        }

    return safe_execute("scene.snapshot", _op, _scene_state_provider)


def tool_scene_snapshot(limit_objects: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Stable public wrapper for Blender tests.
    """
    return run({"limit": limit_objects, "offset": offset})


def tool_scene_snapshot_chunk(token: str) -> Dict[str, Any]:
    """
    Fetch a subsequent chunk using a stateless token.
    """
    decoded = scene_state.decode_token(token)
    return run({"limit": decoded.get("limit"), "offset": decoded.get("offset")})
