from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "tools" / "hera-stdio.ps1"

JSON = Dict[str, Any]


def _send(p: subprocess.Popen, obj: JSON) -> None:
    raw = json.dumps(obj, separators=(",", ":")) + "\n"
    assert p.stdin is not None
    p.stdin.write(raw.encode("utf-8"))
    p.stdin.flush()


def _recv(out_q: "Queue[str]", timeout_s: float = 10.0) -> JSON:
    t0 = time.time()
    while True:
        if time.time() - t0 > timeout_s:
            raise TimeoutError("timeout waiting for JSON-RPC reply on stdout")

        try:
            raw = out_q.get(timeout=0.2)
        except Empty:
            continue

        raw = (raw or "").strip()
        if not raw:
            continue

        return json.loads(raw)


def _start_stdio_server() -> subprocess.Popen:
    if not PS1.exists():
        raise RuntimeError(f"missing {PS1}")

    cmd = [
        str(Path(r"C:\Program Files\PowerShell\7\pwsh.exe")),
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS1),
    ]

    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> None:
    p = _start_stdio_server()
    out_q: "Queue[str]" = Queue()
    err_lines: List[str] = []

    def _pump(stream, q: "Queue[str] | None", sink: List[str] | None):
        while True:
            b = stream.readline()
            if not b:
                break
            s = b.decode("utf-8", errors="replace").rstrip("\r\n")
            if q is not None:
                q.put(s)
            if sink is not None:
                sink.append(s)

    t_out = threading.Thread(target=_pump, args=(p.stdout, out_q, None), daemon=True)  # type: ignore[arg-type]
    t_err = threading.Thread(target=_pump, args=(p.stderr, None, err_lines), daemon=True)  # type: ignore[arg-type]
    t_out.start()
    t_err.start()

    try:
        _send(
            p,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "modeling-demo", "version": "0"}},
            },
        )
        _ = _recv(out_q, timeout_s=20.0)

        batch_steps = [
            {"tool": "hera.blender.mesh.create_cube", "args": {"name": "DemoCube", "size": 1.0, "location": [0, 0, 0]}},
            {"tool": "hera.blender.mesh.create_uv_sphere", "args": {"name": "DemoSphere", "radius": 0.8, "location": [2, 0, 0]}},
            {"tool": "hera.blender.mesh.create_cylinder", "args": {"name": "DemoCyl", "radius": 0.4, "depth": 1.2, "location": [-2, 0, 0]}},
            {"tool": "hera.blender.object.get_transform", "args": {"name": "DemoCube"}},
            {"tool": "hera.blender.object.get_transform", "args": {"name": "DemoSphere"}},
            {"tool": "hera.blender.object.get_transform", "args": {"name": "DemoCyl"}},
            {"tool": "hera.blender.object.delete", "args": {"name": "DemoCube"}},
            {"tool": "hera.blender.object.delete", "args": {"name": "DemoSphere"}},
            {"tool": "hera.blender.object.delete", "args": {"name": "DemoCyl"}},
        ]

        _send(
            p,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "hera.blender.batch", "arguments": {"steps": batch_steps}},
            },
        )
        resp = _recv(out_q, timeout_s=30.0)
        results = resp.get("result", {}).get("content", [{}])[0].get("json", {}).get("results", [])
        for idx, item in enumerate(results):
            if not item.get("ok"):
                raise RuntimeError(f"batch step {idx} failed: {item}")

        print("[demo] batch modeling OK")
    finally:
        try:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
        finally:
            bad = []
            for ln in err_lines:
                if not ln:
                    continue
                if ln.startswith("[hera-stdio]") or ln.startswith("[hera-worker]"):
                    continue
                if "Blender" in ln and "hash" in ln:
                    continue
                bad.append(ln)
            if bad:
                raise RuntimeError("unexpected stderr from hera-stdio.ps1:\n" + "\n".join(bad))


if __name__ == "__main__":
    main()
