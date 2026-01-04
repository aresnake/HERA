"""
Data-first object creation tool (cube, sphere, camera, light).
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

import bmesh

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core import envelope
from hera_mcp.core.coerce import to_name, to_vector3
from hera_mcp.core.queue import mono_queue
from hera_mcp.core.safe_exec import safe_execute


def _bpy():
    return importlib.import_module("bpy")


def _scene(bpy_module):
    if bpy_module.data.scenes:
        return bpy_module.data.scenes[0]
    return bpy_module.context.scene


def _scene_state_provider() -> Dict[str, Any]:
    return scene_state.snapshot().get("scene_state", {})


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


def _create_sphere(bpy_module, name: str, location):
    mesh = bpy_module.data.meshes.new(f"{name}_mesh")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, diameter=1)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy_module.data.objects.new(name, mesh)
    obj.location = location
    return obj


def _create_camera(bpy_module, name: str, location):
    cam_data = bpy_module.data.cameras.new(name=name)
    obj = bpy_module.data.objects.new(name, cam_data)
    obj.location = location
    return obj


def _create_light(bpy_module, name: str, location, light_type: str = "POINT"):
    light_data = bpy_module.data.lights.new(name=name, type=light_type.upper())
    obj = bpy_module.data.objects.new(name, light_data)
    obj.location = location
    return obj


def _creator(kind: str):
    creators = {
        "cube": _create_cube,
        "sphere": _create_sphere,
        "camera": _create_camera,
        "light": _create_light,
    }
    return creators.get(kind)


def run(params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params = params or {}
    kind = str(params.get("type") or params.get("kind") or "cube").lower()
    name = to_name(params.get("name"), fallback=f"{kind}_auto")
    location = to_vector3(params.get("location"))
    light_type = str(params.get("light_type") or "POINT")

    def _op():
        bpy_module = _bpy()
        creator = _creator(kind)
        if not creator:
            return {
                "status": "error",
                "error": envelope.build_error(
                    "invalid_input",
                    f"Unsupported object type: {kind}",
                    recoverable=False,
                ),
            }
        scene = _scene(bpy_module)
        obj = creator(bpy_module, name, location) if kind != "light" else creator(bpy_module, name, location, light_type)
        if scene and scene.collection:
            scene.collection.objects.link(obj)
        diff = {"created": [obj.name], "modified": [], "deleted": []}
        snap = scene_state.snapshot()
        return {
            "status": "success",
            "data": {
                "object": {"name": obj.name, "type": obj.type, "location": list(obj.location)},
                "diff": diff,
            },
            "scene_state": {**(snap.get("scene_state") or {}), "ok": True},
            "resume_token": snap.get("resume_token"),
            "next_actions": snap.get("next_actions"),
        }

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
