"""
Move object tool (translation only).

Now implemented as a thin MCP tool adapter calling the Action Engine.
"""

from __future__ import annotations

from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core.coerce import to_name, to_vector3
from hera_mcp.core.queue import mono_queue
from hera_mcp.core.safe_exec import safe_execute
from hera_mcp.core.actions.models import ActionContext
from hera_mcp.core.actions.runner import run_action


def _scene_state_provider() -> Dict[str, Any]:
    return scene_state.snapshot().get("scene_state", {})


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    name = to_name(params.get("name") or params.get("object"))
    delta = to_vector3(params.get("delta"))
    absolute = params.get("location")
    absolute_loc = to_vector3(absolute) if absolute is not None else None

    action_params: Dict[str, Any] = {"name": name}
    if absolute_loc is not None:
        action_params["location"] = absolute_loc
    else:
        action_params["delta"] = delta

    def _op():
        ctx = ActionContext(scene_state_provider=_scene_state_provider, extras={})
        return run_action("scene.move_object", action_params, ctx)

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
