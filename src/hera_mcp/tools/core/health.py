"""
Healthcheck tool.
"""

from __future__ import annotations

from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core.safe_exec import safe_execute


def _scene_state_provider() -> Dict[str, Any]:
    return scene_state.snapshot().get("scene_state", {})


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Returns a lightweight health envelope with a scene snapshot.
    """
    params = params or {}

    def _op():
        snap = scene_state.snapshot(
            offset=params.get("offset", 0),
            limit=params.get("limit", 100),
        )
        return {
            "data": {"status": "ready", "blender": "headless"},
            "scene_state": snap.get("scene_state"),
            "resume_token": snap.get("resume_token"),
            "next_actions": snap.get("next_actions"),
        }

    return safe_execute("health", _op, _scene_state_provider)
