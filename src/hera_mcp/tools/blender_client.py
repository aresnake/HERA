from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

JSON = Dict[str, Any]


def _port() -> int:
    return int(os.environ.get("HERA_BLENDER_PORT", "8766"))


def _url(path: str) -> str:
    return f"http://127.0.0.1:{_port()}{path}"


def worker_health(timeout_s: float = 5.0) -> JSON:
    req = urllib.request.Request(_url("/health"), method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_worker(timeout_s: float = 15.0) -> None:
    t0 = time.time()
    while True:
        try:
            h = worker_health(timeout_s=2.0)
            if h.get("ok") is True:
                return
        except Exception:
            pass
        if time.time() - t0 > timeout_s:
            raise RuntimeError("Blender worker not reachable on /health")
        time.sleep(0.2)


def call_tool(name: str, arguments: Optional[JSON] = None, timeout_s: float = 10.0) -> JSON:
    payload = {"name": name, "arguments": arguments or {}}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _url("/call"),
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            out = json.loads(resp.read().decode("utf-8"))
            return out
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            return json.loads(raw) if raw else {"ok": False, "error": {"message": str(exc), "type": "HTTPError"}}
        except Exception:
            raise
