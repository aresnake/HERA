"""
Bootstrapping MCP stdio proxy to keep stdout JSON-only while Blender starts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple


CAPABILITIES = {"tools": {}, "resources": {}, "prompts": {}}
READY_TOKEN = "HERA_READY"

TOOLS_LIST = [
    {
        "name": "hera.health",
        "description": "Healthcheck returning a scene snapshot summary.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hera.scene.snapshot",
        "description": "Snapshot the scene objects with chunking support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit_objects": {
                    "type": "integer",
                    "description": "Maximum objects to include.",
                    "default": 100,
                },
                "offset": {
                    "type": "integer",
                    "description": "Start offset for chunking.",
                    "default": 0,
                },
            },
        },
    },
    {
        "name": "hera.scene.snapshot_chunk",
        "description": "Fetch the next chunk using a stateless token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Chunk token from previous snapshot."}
            },
        },
    },
    {
        "name": "hera.scene.create_object",
        "description": "Create a cube, sphere, camera, or light (data-first).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "default": "CUBE"},
                "name": {"type": "string", "default": "Object"},
                "location": {
                    "type": "array",
                    "description": "XYZ coordinates",
                    "default": [0, 0, 0],
                },
                "light_type": {"type": "string", "default": "POINT"},
            },
        },
    },
    {
        "name": "hera.scene.move_object",
        "description": "Move an existing object by delta or absolute location.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Object name to move"},
                "location": {"type": "array", "description": "Absolute location"},
                "delta": {"type": "array", "description": "Delta translation"},
            },
        },
    },
    {
        "name": "hera.ops.status",
        "description": "Check status of a long-running operation.",
        "inputSchema": {
            "type": "object",
            "properties": {"operation_id": {"type": "string", "description": "Operation id"}},
        },
    },
    {
        "name": "hera.ops.cancel",
        "description": "Request cancellation of a long-running operation.",
        "inputSchema": {
            "type": "object",
            "properties": {"operation_id": {"type": "string", "description": "Operation id"}},
        },
    },
    {
        "name": "hera.ops.resume",
        "description": "Resume a partial operation using a resume_token.",
        "inputSchema": {
            "type": "object",
            "properties": {"resume_token": {"type": "string", "description": "Opaque resume token"}},
        },
    },

    {
        "name": "hera.object.get",
        "description": "Inspect an object (type/location/rotation/scale).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Object name to inspect"}
            },
            "required": ["name"]
        },
    },
]


def log_err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def looks_like_jsonrpc(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return False
    markers = ('"jsonrpc"', '"method"', '"result"', '"id"')
    return any(m in stripped for m in markers)


def bootstrap_response(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    rid = req.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "hera-mcp-proxy", "version": "0.1.0"},
                "capabilities": CAPABILITIES,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {"ok": True}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS_LIST}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"resources": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"prompts": []}}
    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": rid, "result": {"ok": True}}
    if method == "exit":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    return None


class Proxy:
    def __init__(self, child_cmd: List[str]) -> None:
        self.child_cmd = child_cmd
        self.child: Optional[subprocess.Popen] = None
        self.ready = threading.Event()
        self.shutdown = threading.Event()
        self.exit_code: Optional[int] = None
        self.queue: List[Tuple[Any, str]] = []
        self.queue_lock = threading.Lock()
        self.queue_max = 25
        self.flushed_on_ready = False

    def start_child(self) -> None:
        self.child = subprocess.Popen(
            self.child_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            text=True,
            encoding="utf-8",
        )

    def enqueue_request(self, req_id: Any, raw_line: str) -> None:
        with self.queue_lock:
            if len(self.queue) >= self.queue_max:
                dropped = self.queue.pop(0)
                log_err(f"[proxy] queue full; dropping oldest id={dropped[0]}")
            self.queue.append((req_id, raw_line))

    def flush_queued(self) -> None:
        if not self.child or not self.child.stdin:
            return
        with self.queue_lock:
            if not self.queue:
                return
            items = list(self.queue)
            self.queue.clear()
            self.flushed_on_ready = True
        for _, line in items:
            try:
                self.child.stdin.write(line + "\n")
                self.child.stdin.flush()
            except Exception as exc:
                log_err(f"[proxy] failed to flush queued request: {exc}")

    def mark_ready(self) -> None:
        if not self.ready.is_set():
            self.ready.set()
        if not self.flushed_on_ready:
            self.flush_queued()

    def pump_child_stdout(self) -> None:
        assert self.child and self.child.stdout
        for line in self.child.stdout:
            if looks_like_jsonrpc(line):
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                sys.stderr.write(f"[child-stdout] {line}")
                sys.stderr.flush()

    def pump_child_stderr(self) -> None:
        assert self.child and self.child.stderr
        for line in self.child.stderr:
            if READY_TOKEN in line:
                self.mark_ready()
            sys.stderr.write(f"[child-stderr] {line}")
            sys.stderr.flush()

    def handle_parent_stdin(self) -> None:
        """
        Consume parent stdin lines; if ready, forward; else handle bootstrap or queue.
        """
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception:
                log_err(f"[proxy] invalid JSON from parent: {line}")
                continue

            method = req.get("method")
            if method == "exit":
                self.shutdown.set()
            if method == "shutdown":
                self.shutdown.set()

            if not self.ready.is_set():
                resp = bootstrap_response(req)
                if resp:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
                    if method in ("shutdown", "exit"):
                        self.shutdown.set()
                        break
                    continue
                if method == "tools/call":
                    self.enqueue_request(req.get("id"), line)
                    log_err(f"[proxy] queued tools/call id={req.get('id')} (booting)")
                else:
                    self.enqueue_request(req.get("id"), line)
                continue

            try:
                self.child.stdin.write(line + "\n")
                self.child.stdin.flush()
            except Exception as exc:
                log_err(f"[proxy] failed to write to child: {exc}")
                break

            if method in ("shutdown", "exit"):
                self.shutdown.set()
                break
        if self.ready.is_set():
            self.flush_queued()
        self.shutdown.set()

    def run(self) -> int:
        self.start_child()

        stdout_thread = threading.Thread(target=self.pump_child_stdout, daemon=True)
        stderr_thread = threading.Thread(target=self.pump_child_stderr, daemon=True)
        stdin_thread = threading.Thread(target=self.handle_parent_stdin, daemon=True)

        stdout_thread.start()
        stderr_thread.start()
        stdin_thread.start()

        code = self.child.wait()
        self.shutdown.set()
        if not self.ready.is_set():
            with self.queue_lock:
                queued = list(self.queue)
                self.queue.clear()
            for req_id, _ in queued:
                if req_id is None:
                    continue
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": "Backend exited before ready"}],
                    },
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        stdin_thread.join(timeout=1)
        return code


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrapping MCP stdio proxy.")
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        log_err("No child command provided to stdio_proxy.")
        return 1
    proxy = Proxy(cmd)
    return proxy.run()


if __name__ == "__main__":
    sys.exit(main())
