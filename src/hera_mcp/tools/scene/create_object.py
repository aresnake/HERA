"""
Data-first object creation tool (cube, sphere, camera, light).

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

    # Keep light coercion here for stable defaults / MVP parity
    kind = str(params.get("type") or params.get("kind") or "cube").lower()
    name = to_name(params.get("name"), fallback=f"{kind}_auto")
    location = to_vector3(params.get("location"))
    light_type = str(params.get("light_type") or "POINT")

    action_params = {
        "type": kind,
        "name": name,
        "location": location,
        "light_type": light_type,
    }

    def _op():
        ctx = ActionContext(scene_state_provider=_scene_state_provider, extras={})
        return run_action("scene.create_object", action_params, ctx)

    return mono_queue.run(lambda: safe_execute("scene.create_object", _op, _scene_state_provider))


def tool_create_object(
    type: str = "CUBE",
    name: str = "Object",
    location=None,
    light_type: str = "POINT",
    **kwargs,
) -> Dict[str, Any]:
    """
    Stable public wrapper for Blender tests.
    """
    params = {
        "type": type,
        "name": name,
        "location": location,
        "light_type": light_type,
    }
    params.update(kwargs)
    return run(params)
