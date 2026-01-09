from __future__ import annotations

import json
import os
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

import bpy

JSON = Dict[str, Any]


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


class Job:
    def __init__(self, name: str, args: JSON):
        self.name = name
        self.args = args
        self.done = threading.Event()
        self.result: Optional[JSON] = None
        self.error: Optional[JSON] = None


JOB_Q: "queue.Queue[Job]" = queue.Queue()


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
    _scene_for_link().collection.objects.link(obj)


def _list_objects() -> JSON:
    _ensure_cube()
    names = sorted(obj.name for obj in bpy.data.objects)
    return {"objects": names, "count": len(names)}


def _move_object(args: JSON) -> JSON:
    name = args.get("name")
    location = args.get("location")

    if not isinstance(name, str) or not name:
        raise ToolError("invalid_arguments", "name must be a non-empty string")
    if not isinstance(location, (list, tuple)) or len(location) != 3:
        raise ToolError("invalid_arguments", "location must be an array of 3 numbers")

    try:
        loc = (float(location[0]), float(location[1]), float(location[2]))
    except Exception as exc:
        raise ToolError("invalid_arguments", "location must contain numbers") from exc

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
    if name == "ping":
        return {"pong": True, "blender": _blender_version()}
    if name == "blender.version":
        return _blender_version_details()
    if name in ("list_objects", "blender.scene.list_objects"):
        return _list_objects()
    if name == "blender.object.move":
        return _move_object(args)
    if name == "blender.object.exists":
        return _object_exists(args)
    if name == "blender.object.get_location":
        return _object_get_location(args)
    if name == "blender.scene.get_active_object":
        return _scene_get_active_object()
    if name == "blender.batch":
        return _batch(args)
    raise ValueError(f"Unknown tool: {name}")


def _write_ready_file(path_str: str, payload: JSON) -> str:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(str(tmp), str(p))
    return str(p)


def _parse_after_double_dash() -> Dict[str, str]:
    """
    Blender passes script args after '--'.
    We parse *only* after '--' to avoid Blender's own args.
    Supports: --port <int> --ready-file <path>
    """
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    out: Dict[str, str] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--port", "--ready-file"):
            if i + 1 < len(argv):
                out[a] = argv[i + 1]
                i += 2
                continue
        i += 1
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "HERAWorker/0.1"

    def _send(self, code: int, payload: JSON) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "blender": _blender_version()})
            return
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/call":
            self._send(404, {"ok": False, "error": "not_found"})
            return

        n = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"

        try:
            req = json.loads(raw) if raw else {}
            name = req.get("name")
            args = req.get("arguments") or {}
            if not isinstance(name, str) or not name:
                self._send(400, {"ok": False, "error": {"message": "missing name"}})
                return

            job = Job(name=name, args=args)
            JOB_Q.put(job)

            if not job.done.wait(timeout=20.0):
                self._send(504, {"ok": False, "error": {"message": "timeout_waiting_main_thread"}})
                return

            if job.error:
                self._send(500, job.error)
                return

            self._send(200, job.result or {"ok": False, "error": {"message": "unknown"}})

        except Exception as exc:
            self._send(500, {"ok": False, "error": {"message": str(exc), "type": type(exc).__name__}})

    def log_message(self, format, *args):
        return


def main() -> None:
    parsed = _parse_after_double_dash()
    port = int(parsed.get("--port", "8766") or "8766")
    ready_file = parsed.get("--ready-file", "") or ""

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    port = int(httpd.server_address[1])

    t = threading.Thread(target=httpd.serve_forever, name="hera-httpd", daemon=True)
    t.start()

    msg = {
        "ok": True,
        "blender": _blender_version(),
        "port": port,
        "cwd": str(Path.cwd()),
        "sys_argv": list(sys.argv),
        "parsed_after_--": parsed,
    }
    print(f"[hera-worker] {msg}", flush=True)

    if ready_file:
        try:
            written = _write_ready_file(ready_file, msg)
            print(f"[hera-worker] ready-file written: {written}", flush=True)
        except Exception as exc:
            print(f"[hera-worker] ready-file FAILED: {exc!r}", flush=True)

    try:
        while True:
            try:
                job = JOB_Q.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                out = _dispatch_tool(job.name, job.args)
                job.result = {"ok": True, "result": out}
            except ToolError as exc:
                job.error = exc.to_error()
            except Exception as exc:
                job.error = {"ok": False, "error": {"message": str(exc), "type": type(exc).__name__}}
            finally:
                job.done.set()
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
