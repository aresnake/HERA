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


def _dispatch_tool(name: str, args: JSON) -> JSON:
    if name == "ping":
        return {"pong": True, "blender": _blender_version()}
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
            except Exception as exc:
                job.error = {"ok": False, "error": {"message": str(exc), "type": type(exc).__name__}}
            finally:
                job.done.set()
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
