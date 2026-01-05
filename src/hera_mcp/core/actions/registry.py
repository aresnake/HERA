"""
Action registry + built-in actions.

Design:
- Keep MCP tool surface stable.
- Implement Blender operations in actions, not tools.
- Tools become adapters: parse -> run action -> safe_execute envelope.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core import envelope
from hera_mcp.core.coerce import to_name, to_vector3

from .models import ActionContext, ActionOutput


# ---------------------------
# Registry
# ---------------------------

_ACTIONS: Dict[str, Any] = {}


def register(action_name: str, action_impl: Any) -> None:
    _ACTIONS[action_name] = action_impl


def get(action_name: str) -> Optional[Any]:
    return _ACTIONS.get(action_name)


def list_actions() -> Dict[str, str]:
    return {name: getattr(impl, "__doc__", "") or "" for name, impl in _ACTIONS.items()}


# ---------------------------
# Blender helpers (lazy)
# ---------------------------

def _bpy():
    return importlib.import_module("bpy")


def _scene(bpy_module):
    if bpy_module.data.scenes:
        return bpy_module.data.scenes[0]
    return bpy_module.context.scene


# ---------------------------
# Built-in Actions
# ---------------------------

class SceneCreateObject:
    """
    Create a cube, sphere, camera, or light (data-first).
    Params: type/kind, name, location, light_type
    """

    name = "scene.create_object"

    @staticmethod
    def _create_cube(bpy_module, name: str, location):
        mesh = bpy_module.data.meshes.new(f"{name}_mesh")
        verts = [
            (-0.5, -0.5, -0.5),
            (0.5, -0.5, -0.5),
            (0.5, 0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (-0.5, -0.5, 0.5),
            (0.5, -0.5, 0.5),
            (0.5, 0.5, 0.5),
            (-0.5, 0.5, 0.5),
        ]
        faces = [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (1, 2, 6, 5),
            (0, 3, 7, 4),
        ]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy_module.data.objects.new(name, mesh)
        obj.location = location
        return obj

    @staticmethod
    def _create_sphere(bpy_module, name: str, location):
        mesh = bpy_module.data.meshes.new(f"{name}_mesh")
        try:
            import bmesh
        except Exception as exc:  # pragma: no cover - requires Blender runtime
            raise RuntimeError(f"bmesh not available: {exc}") from exc

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, diameter=1)
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        obj = bpy_module.data.objects.new(name, mesh)
        obj.location = location
        return obj

    @staticmethod
    def _create_camera(bpy_module, name: str, location):
        cam_data = bpy_module.data.cameras.new(name=name)
        obj = bpy_module.data.objects.new(name, cam_data)
        obj.location = location
        return obj

    @staticmethod
    def _create_light(bpy_module, name: str, location, light_type: str = "POINT"):
        light_data = bpy_module.data.lights.new(name=name, type=light_type.upper())
        obj = bpy_module.data.objects.new(name, light_data)
        obj.location = location
        return obj

    @classmethod
    def _creator(cls, kind: str):
        creators = {
            "cube": cls._create_cube,
            "sphere": cls._create_sphere,
            "camera": cls._create_camera,
            "light": cls._create_light,
        }
        return creators.get(kind)

    def execute(self, params: Dict[str, Any], ctx: ActionContext) -> ActionOutput:
        kind = str(params.get("type") or params.get("kind") or "cube").lower()
        name = to_name(params.get("name"), fallback=f"{kind}_auto")
        location = to_vector3(params.get("location"))
        light_type = str(params.get("light_type") or "POINT")

        bpy_module = _bpy()
        creator = self._creator(kind)
        if not creator:
            return ActionOutput(
                status="error",
                error=envelope.build_error(
                    "invalid_input",
                    f"Unsupported object type: {kind}",
                    recoverable=False,
                ),
            )

        scene = _scene(bpy_module)
        obj = creator(bpy_module, name, location) if kind != "light" else creator(bpy_module, name, location, light_type)
        if scene and scene.collection:
            scene.collection.objects.link(obj)

        diff = {"created": [obj.name], "modified": [], "deleted": []}
        snap = scene_state.snapshot()

        return ActionOutput(
            status="success",
            data={
                "object": {"name": obj.name, "type": obj.type, "location": list(obj.location)},
                "diff": diff,
            },
            scene_state={**(snap.get("scene_state") or {}), "ok": True},
            resume_token=snap.get("resume_token"),
            next_actions=snap.get("next_actions"),
        )


class SceneMoveObject:
    """
    Move an existing object by delta or absolute location.
    Params: name/object, location, delta
    """

    name = "scene.move_object"

    def execute(self, params: Dict[str, Any], ctx: ActionContext) -> ActionOutput:
        name = to_name(params.get("name") or params.get("object"))
        delta = to_vector3(params.get("delta"))
        absolute = params.get("location")
        absolute_loc = to_vector3(absolute) if absolute is not None else None

        bpy_module = _bpy()
        obj = bpy_module.data.objects.get(name)
        if obj is None:
            return ActionOutput(
                status="error",
                error=envelope.build_error(
                    "not_found",
                    f"Object not found: {name}",
                    recoverable=False,
                ),
            )

        if absolute_loc is not None:
            obj.location = absolute_loc
        else:
            current = to_vector3(getattr(obj, "location", (0.0, 0.0, 0.0)))
            obj.location = (
                float(current[0]) + delta[0],
                float(current[1]) + delta[1],
                float(current[2]) + delta[2],
            )

        diff = {"created": [], "modified": [obj.name], "deleted": []}
        snap = scene_state.snapshot()

        return ActionOutput(
            status="success",
            data={"object": {"name": obj.name, "location": list(obj.location)}, "diff": diff},
            scene_state={**(snap.get("scene_state") or {}), "ok": True},
            resume_token=snap.get("resume_token"),
            next_actions=snap.get("next_actions"),
        )


# Register defaults at import time (simple MVP)
register(SceneCreateObject.name, SceneCreateObject())
register(SceneMoveObject.name, SceneMoveObject())
