from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
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

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"non-JSON on stdout: {raw!r}") from exc


def main() -> None:
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

    p = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

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
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "hera-smoke", "version": "0"}},
            },
        )
        init_resp = _recv(out_q, timeout_s=15.0)
        assert init_resp.get("id") == 1, init_resp
        assert "result" in init_resp, init_resp

        _send(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        list_resp = _recv(out_q, timeout_s=15.0)
        assert list_resp.get("id") == 2, list_resp
        assert "result" in list_resp, list_resp

        tools = list_resp["result"]["tools"]
        names = [t.get("name") for t in tools]
        assert "hera.ping" in names
        assert "hera.blender.version" in names
        assert "hera.blender.scene.list_objects" in names
        assert "hera.blender.object.move" in names

        _send(p, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.ping", "arguments": {}}})
        ping_resp = _recv(out_q, timeout_s=15.0)
        assert ping_resp.get("id") == 3, ping_resp
        assert ping_resp.get("result", {}).get("content") is not None, ping_resp

        _send(
            p,
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "hera.blender.version", "arguments": {}}},
        )
        ver_resp = _recv(out_q, timeout_s=15.0)
        ver_json = ver_resp.get("result", {}).get("content", [{}])[0].get("json", {})
        assert "blender_version" in ver_json, ver_resp

        _send(
            p,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "hera.blender.scene.list_objects", "arguments": {}},
            },
        )
        list_resp2 = _recv(out_q, timeout_s=15.0)
        list_json = list_resp2.get("result", {}).get("content", [{}])[0].get("json", {})
        assert "Cube" in list_json.get("objects", []), list_resp2

        _send(
            p,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "hera.blender.object.move", "arguments": {"name": "Cube", "location": [1, 2, 3]}},
            },
        )
        move_resp = _recv(out_q, timeout_s=15.0)
        move_json = move_resp.get("result", {}).get("content", [{}])[0].get("json", {})
        assert move_json.get("name") == "Cube", move_resp
        assert move_json.get("location") == [1.0, 2.0, 3.0], move_resp

        _send(
            p,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "hera.blender.scene.list_objects", "arguments": {}},
            },
        )
        list_resp3 = _recv(out_q, timeout_s=15.0)
        list_json3 = list_resp3.get("result", {}).get("content", [{}])[0].get("json", {})
        assert "Cube" in list_json3.get("objects", []), list_resp3

        print("[smoke] OK initialize + tools/list + tools/call(hera.ping) + blender tools")

    finally:
        try:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
        finally:
            # allow launcher logs (stderr)
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
