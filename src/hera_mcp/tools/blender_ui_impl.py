from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

import os

import queue
import threading

import bpy
import bmesh

JSON = Dict[str, Any]

_JOB_QUEUE: "queue.Queue[_Job]" = queue.Queue()
_SCHEDULER_READY = False
_SCHEDULER_REGISTERED = False
_SCHEDULER_LOCK = threading.Lock()
_DEFAULT_TIMEOUT_S = 30.0
try:
    _MAIN_THREAD_TIMEOUT_S = float(os.environ.get("HERA_BLENDER_TIMEOUT", _DEFAULT_TIMEOUT_S))
except Exception:
    _MAIN_THREAD_TIMEOUT_S = _DEFAULT_TIMEOUT_S


class ToolError(Exception):
    def __init__(self, code: str, message: str, details: Optional[JSON] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_error(self) -> JSON:
        payload: JSON = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return {"ok": False, "error": payload}


class _Job:
    __slots__ = ("tool", "args", "done", "result")

    def __init__(self, tool: str, args: JSON):
        self.tool = tool
        self.args = args
        self.done = threading.Event()
        self.result: Optional[JSON] = None


def _execute_tool(tool: str, args: JSON) -> JSON:
    try:
        out = _dispatch_tool(tool, args)
        return {"ok": True, "result": out}
    except ToolError as exc:
        return exc.to_error()
    except Exception as exc:
        return {
            "ok": False,
            "error": {"code": "internal_error", "message": str(exc), "type": type(exc).__name__},
        }


def _drain_queue() -> float:
    global _SCHEDULER_READY
    if not _SCHEDULER_READY:
        _SCHEDULER_READY = True
    while True:
        try:
            job = _JOB_QUEUE.get_nowait()
        except queue.Empty:
            break
        job.result = _execute_tool(job.tool, job.args)
        job.done.set()
    return 0.1


def init_main_thread() -> bool:
    global _SCHEDULER_REGISTERED
    if threading.current_thread() is not threading.main_thread():
        return False
    with _SCHEDULER_LOCK:
        if _SCHEDULER_REGISTERED:
            return True
        bpy.app.timers.register(_drain_queue, first_interval=0.0, persistent=True)
        _SCHEDULER_REGISTERED = True
    return True


def _ensure_scheduler() -> bool:
    if _SCHEDULER_READY or _SCHEDULER_REGISTERED:
        return True
    if threading.current_thread() is threading.main_thread():
        return init_main_thread()
    return False


def _blender_version() -> str:
    v = bpy.app.version
    return ".".join(str(x) for x in v)


def _blender_version_details() -> JSON:
    def _maybe_str(value: Any) -> Optional[str]:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            return value
        return None

    version_raw = getattr(bpy.app, "version_string", None)
    version_str = _maybe_str(version_raw) or _blender_version()
    build_date = getattr(bpy.app, "build_date", None)
    build_hash = getattr(bpy.app, "build_hash", None)

    build_date_str: Optional[str] = None
    if isinstance(build_date, (tuple, list)) and len(build_date) >= 3:
        build_date_str = f"{int(build_date[0]):04d}-{int(build_date[1]):02d}-{int(build_date[2]):02d}"
    elif isinstance(build_date, str):
        build_date_str = build_date or None

    return {
        "blender_version": version_str,
        "build_date": build_date_str,
        "hash": _maybe_str(build_hash) or None,
    }


def _scene_for_link() -> bpy.types.Scene:
    if bpy.data.scenes:
        return bpy.data.scenes[0]
    return bpy.context.scene


def _link_object(obj: bpy.types.Object) -> None:
    try:
        ctx = bpy.context
        if hasattr(ctx, "scene") and ctx.scene is not None:
            ctx.scene.collection.objects.link(obj)
            return
    except Exception:
        pass
    _scene_for_link().collection.objects.link(obj)


def _unique_object_name(base: str) -> str:
    if bpy.data.objects.get(base) is None:
        return base
    i = 1
    while True:
        candidate = f"{base}.{i:03d}"
        if bpy.data.objects.get(candidate) is None:
            return candidate
        i += 1


def _vec3(value: Any, name: str) -> Sequence[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ToolError("invalid_arguments", f"{name} must be an array of 3 numbers")
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception as exc:
        raise ToolError("invalid_arguments", f"{name} must contain numbers") from exc


def _ensure_cube() -> None:
    if bpy.data.objects.get("Cube"):
        return
    if len(bpy.data.objects) > 0:
        return

    verts = [
        (-1.0, -1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, 1.0, 1.0),
        (1.0, -1.0, -1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, -1.0),
        (1.0, 1.0, 1.0),
    ]
    faces = [
        (0, 4, 6, 2),
        (1, 3, 7, 5),
        (0, 1, 5, 4),
        (2, 6, 7, 3),
        (0, 2, 3, 1),
        (4, 5, 7, 6),
    ]

    mesh = bpy.data.meshes.new("CubeMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Cube", mesh)
    _link_object(obj)


def _list_objects() -> JSON:
    _ensure_cube()
    names = sorted(obj.name for obj in bpy.data.objects)
    return {"objects": names, "count": len(names)}


def _move_object(args: JSON) -> JSON:
    name = args.get("name")
    location = args.get("location")

    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    loc = _vec3(location, "location")

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ToolError("object_not_found", f"object not found: {name}", {"name": name})

    obj.location = loc
    return {"name": obj.name, "location": [float(obj.location[0]), float(obj.location[1]), float(obj.location[2])]}


def _object_exists(args: JSON) -> JSON:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    return {"name": name, "exists": bpy.data.objects.get(name) is not None}


def _object_get_location(args: JSON) -> JSON:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ToolError("not_found", f"object not found: {name}", {"name": name})
    return {"name": obj.name, "location": [float(obj.location[0]), float(obj.location[1]), float(obj.location[2])]}


def _scene_get_active_object() -> JSON:
    try:
        ctx = bpy.context
    except Exception:
        return {"name": None}
    try:
        obj = ctx.active_object
    except Exception:
        return {"name": None}
    if obj is None:
        return {"name": None}
    return {"name": obj.name}


def _create_mesh_object(base_name: str, bm: bmesh.types.BMesh, location: Sequence[float]) -> JSON:
    obj_name = _unique_object_name(base_name)
    mesh = bpy.data.meshes.new(f"{obj_name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(obj_name, mesh)
    _link_object(obj)
    obj.location = location
    return {
        "name": obj.name,
        "created": True,
        "location": [float(obj.location[0]), float(obj.location[1]), float(obj.location[2])],
    }


def _mesh_create_cube(args: JSON) -> JSON:
    name = args.get("name") or "Cube"
    size = args.get("size", 2.0)
    location = args.get("location", (0.0, 0.0, 0.0))

    if not isinstance(name, str):
        raise ToolError("invalid_arguments", "name must be a string")
    try:
        size_f = float(size)
    except Exception as exc:
        raise ToolError("invalid_arguments", "size must be a number") from exc
    loc = _vec3(location, "location")

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size_f)
    return _create_mesh_object(name, bm, loc)


def _mesh_create_uv_sphere(args: JSON) -> JSON:
    name = args.get("name") or "Sphere"
    radius = args.get("radius", 1.0)
    segments = args.get("segments", 32)
    rings = args.get("rings", 16)
    location = args.get("location", (0.0, 0.0, 0.0))

    if not isinstance(name, str):
        raise ToolError("invalid_arguments", "name must be a string")
    try:
        radius_f = float(radius)
    except Exception as exc:
        raise ToolError("invalid_arguments", "radius must be a number") from exc
    try:
        segments_i = int(segments)
        rings_i = int(rings)
    except Exception as exc:
        raise ToolError("invalid_arguments", "segments and rings must be integers") from exc
    loc = _vec3(location, "location")

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments_i, v_segments=rings_i, radius=radius_f)
    return _create_mesh_object(name, bm, loc)


def _mesh_create_cylinder(args: JSON) -> JSON:
    name = args.get("name") or "Cylinder"
    radius = args.get("radius", 1.0)
    depth = args.get("depth", 2.0)
    vertices = args.get("vertices", 32)
    location = args.get("location", (0.0, 0.0, 0.0))

    if not isinstance(name, str):
        raise ToolError("invalid_arguments", "name must be a string")
    try:
        radius_f = float(radius)
        depth_f = float(depth)
    except Exception as exc:
        raise ToolError("invalid_arguments", "radius and depth must be numbers") from exc
    try:
        vertices_i = int(vertices)
    except Exception as exc:
        raise ToolError("invalid_arguments", "vertices must be an integer") from exc
    loc = _vec3(location, "location")

    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        segments=vertices_i,
        radius1=radius_f,
        radius2=radius_f,
        depth=depth_f,
        cap_ends=True,
    )
    return _create_mesh_object(name, bm, loc)


def _object_rename(args: JSON) -> JSON:
    src = args.get("from")
    dst = args.get("to")
    if not isinstance(src, str) or not src:
        raise ToolError("invalid_arguments", "from must be a non-empty string")
    if not isinstance(dst, str) or not dst:
        raise ToolError("invalid_arguments", "to must be a non-empty string")

    obj = bpy.data.objects.get(src)
    if obj is None:
        raise ToolError("not_found", f"object not found: {src}", {"name": src})
    if bpy.data.objects.get(dst) is not None:
        raise ToolError("already_exists", f"object already exists: {dst}", {"name": dst})

    obj.name = dst
    return {"from": src, "to": obj.name}


def _object_delete(args: JSON) -> JSON:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ToolError("not_found", f"object not found: {name}", {"name": name})
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"name": name, "deleted": True}


def _object_set_transform(args: JSON) -> JSON:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ToolError("not_found", f"object not found: {name}", {"name": name})

    if "location" in args:
        obj.location = _vec3(args.get("location"), "location")
    if "rotation_euler" in args:
        obj.rotation_euler = _vec3(args.get("rotation_euler"), "rotation_euler")
    if "scale" in args:
        obj.scale = _vec3(args.get("scale"), "scale")

    return {
        "name": obj.name,
        "location": [float(obj.location[0]), float(obj.location[1]), float(obj.location[2])],
        "rotation_euler": [
            float(obj.rotation_euler[0]),
            float(obj.rotation_euler[1]),
            float(obj.rotation_euler[2]),
        ],
        "scale": [float(obj.scale[0]), float(obj.scale[1]), float(obj.scale[2])],
    }


def _object_get_transform(args: JSON) -> JSON:
    name = args.get("name")
    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ToolError("not_found", f"object not found: {name}", {"name": name})
    return {
        "name": obj.name,
        "location": [float(obj.location[0]), float(obj.location[1]), float(obj.location[2])],
        "rotation_euler": [
            float(obj.rotation_euler[0]),
            float(obj.rotation_euler[1]),
            float(obj.rotation_euler[2]),
        ],
        "scale": [float(obj.scale[0]), float(obj.scale[1]), float(obj.scale[2])],
    }


def _batch(args: JSON) -> JSON:
    steps = args.get("steps")
    continue_on_error = args.get("continue_on_error", False)

    if not isinstance(steps, list):
        raise ToolError("invalid_arguments", "steps must be an array")
    if not isinstance(continue_on_error, bool):
        raise ToolError("invalid_arguments", "continue_on_error must be a boolean")

    allowed_internal = {
        "blender.version",
        "blender.scene.list_objects",
        "blender.object.move",
        "blender.object.exists",
        "blender.object.get_location",
        "blender.scene.get_active_object",
        "blender.mesh.create_cube",
        "blender.mesh.create_uv_sphere",
        "blender.mesh.create_cylinder",
        "blender.object.rename",
        "blender.object.delete",
        "blender.object.set_transform",
        "blender.object.get_transform",
    }

    def _step_error(tool_name: str, code: str, message: str, details: Optional[JSON] = None) -> JSON:
        err: JSON = {"code": code, "message": message}
        if details is not None:
            err["details"] = details
        return {"ok": False, "tool": tool_name, "error": err}

    results: list[JSON] = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            results.append(_step_error("<invalid>", "invalid_step", "step must be an object", {"index": idx}))
            if not continue_on_error:
                break
            continue

        tool_name = step.get("tool")
        step_args = step.get("args") if "args" in step else {}

        if not isinstance(tool_name, str) or not tool_name:
            results.append(_step_error("<invalid>", "invalid_tool", "tool must be a non-empty string", {"index": idx}))
            if not continue_on_error:
                break
            continue

        if not tool_name.startswith("hera.blender.") or tool_name == "hera.blender.batch":
            results.append(
                _step_error(tool_name, "forbidden_tool", "tool not allowed in batch", {"tool": tool_name})
            )
            if not continue_on_error:
                break
            continue

        if not isinstance(step_args, dict):
            results.append(
                _step_error(tool_name, "invalid_arguments", "args must be an object", {"tool": tool_name})
            )
            if not continue_on_error:
                break
            continue

        internal_tool = tool_name.replace("hera.", "", 1)
        if internal_tool not in allowed_internal:
            results.append(_step_error(tool_name, "unknown_tool", "unknown tool", {"tool": tool_name}))
            if not continue_on_error:
                break
            continue

        try:
            out = _dispatch_tool(internal_tool, step_args)
            results.append({"ok": True, "tool": tool_name, "result": out})
        except ToolError as exc:
            results.append({"ok": False, "tool": tool_name, "error": exc.to_error().get("error")})
            if not continue_on_error:
                break
        except Exception as exc:
            results.append(
                {
                    "ok": False,
                    "tool": tool_name,
                    "error": {"message": str(exc), "type": type(exc).__name__},
                }
            )
            if not continue_on_error:
                break

    return {"results": results}


def _dispatch_tool(name: str, args: JSON) -> JSON:
    if name == "blender.version":
        return _blender_version_details()
    if name in ("list_objects", "blender.scene.list_objects"):
        return _list_objects()
    if name == "blender.scene.get_active_object":
        return _scene_get_active_object()
    if name == "blender.object.exists":
        return _object_exists(args)
    if name == "blender.object.get_location":
        return _object_get_location(args)
    if name == "blender.object.move":
        return _move_object(args)
    if name == "blender.mesh.create_cube":
        return _mesh_create_cube(args)
    if name == "blender.mesh.create_uv_sphere":
        return _mesh_create_uv_sphere(args)
    if name == "blender.mesh.create_cylinder":
        return _mesh_create_cylinder(args)
    if name == "blender.object.rename":
        return _object_rename(args)
    if name == "blender.object.delete":
        return _object_delete(args)
    if name == "blender.object.set_transform":
        return _object_set_transform(args)
    if name == "blender.object.get_transform":
        return _object_get_transform(args)
    if name == "blender.batch":
        return _batch(args)
    if name == "create_cube":
        return _mesh_create_cube(args)
    raise ValueError(f"Unknown tool: {name}")


def call(tool: str, args: JSON) -> JSON:
    if threading.current_thread() is threading.main_thread():
        return _execute_tool(tool, args)

    _ensure_scheduler()

    job = _Job(tool, args)
    _JOB_QUEUE.put(job)
    if not job.done.wait(_MAIN_THREAD_TIMEOUT_S):
        return {"ok": False, "error": {"code": "timeout", "message": "Timed out waiting for Blender main thread"}}
    return job.result or {"ok": False, "error": {"code": "internal_error", "message": "No result from job"}}
