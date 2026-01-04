from __future__ import annotations

from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core.safe_exec import safe_execute


def _scene_state_provider() -> Dict[str, Any]:
    snap = scene_state.snapshot()
    ss = snap.get("scene_state") or {}
    return {**ss, "ok": True}


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Health check envelope; always includes scene_state.
    """
    params = params or {}

    def _op():
        snap = scene_state.snapshot(
            offset=int(params.get("offset") or 0),
            limit=int(params.get("limit") or 25),
        )
        ss = snap.get("scene_state") or {}
        ss = {**ss, "ok": True}
        return {
            "status": "success",
            "data": {"ok": True, "diff": {"created": [], "modified": [], "deleted": []}},
            "scene_state": ss,
            "resume_token": snap.get("resume_token"),
            "next_actions": snap.get("next_actions"),
        }

    return safe_execute("hera.health", _op, _scene_state_provider)


def tool_health() -> Dict[str, Any]:
    """
    Stable public wrapper for Blender tests.
    """
    return run()
