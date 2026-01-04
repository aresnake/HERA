from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, Optional


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)


def _is_jsonrpc(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("jsonrpc") == "2.0" and ("result" in obj or "error" in obj)


def read_jsonrpc_line(p: subprocess.Popen, timeout_s: float = 10.0) -> Dict[str, Any]:
    """
    Read lines from p.stdout until we find a valid JSON-RPC object.
    Ignore empty lines and non-JSON lines (some hosts/proxies can leak noise).
    """
    assert p.stdout is not None
    deadline = time.time() + timeout_s
    buf = b""

    while time.time() < deadline:
        chunk = p.stdout.read(1)
        if not chunk:
            # process may not have produced output yet; small sleep prevents busy loop
            time.sleep(0.01)
            continue

        buf += chunk
        if chunk != b"\n":
            continue

        line = buf.decode("utf-8", errors="replace").strip()
        buf = b""

        if not line:
            continue

        # Some wrappers prefix lines (rare). Try to locate JSON object.
        s = line
        if "{" in s and not s.lstrip().startswith("{"):
            s = s[s.find("{") :]

        try:
            obj = json.loads(s)
        except Exception:
            # ignore noise; keep going
            eprint("[smoke] ignored non-JSON line:", line[:200])
            continue

        if _is_jsonrpc(obj):
            return obj

        # valid JSON but not JSON-RPC -> ignore
        eprint("[smoke] ignored JSON non-JSONRPC line:", s[:200])

    raise TimeoutError("Timeout waiting for JSON-RPC response on stdout.")


def rpc(p: subprocess.Popen, req: Dict[str, Any], timeout_s: float = 10.0) -> Dict[str, Any]:
    assert p.stdin is not None
    msg = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")
    p.stdin.write(msg)
    p.stdin.flush()
    return read_jsonrpc_line(p, timeout_s=timeout_s)


def main() -> int:
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    launcher = os.path.join(repo, "tools", "hera-stdio.ps1")

    cmd = ["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", launcher]
    eprint("[smoke] launching:", " ".join(cmd))

    p = subprocess.Popen(
        cmd,
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    # pump stderr so buffers don't block
    def pump_err() -> None:
        assert p.stderr is not None
        for raw in iter(p.stderr.readline, b""):
            s = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if s:
                eprint("[server-stderr] " + s)

    import threading

    threading.Thread(target=pump_err, daemon=True).start()

    # initialize (Claude-like)
    r1 = rpc(
        p,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "hera-smoke-claude", "version": "0.0"},
                "capabilities": {},
            },
        },
        timeout_s=15.0,
    )
    eprint("[smoke] initialize ok")

    # tools/list
    r2 = rpc(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout_s=10.0)
    eprint("[smoke] tools/list ok")

    # optional Claude calls (we accept stubs)
    _ = rpc(p, {"jsonrpc": "2.0", "id": 20, "method": "resources/list", "params": {}}, timeout_s=10.0)
    eprint("[smoke] resources/list ok")
    _ = rpc(p, {"jsonrpc": "2.0", "id": 21, "method": "prompts/list", "params": {}}, timeout_s=10.0)
    eprint("[smoke] prompts/list ok")

    # tools/call health
    r3 = rpc(
        p,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.health", "arguments": {}}},
        timeout_s=10.0,
    )
    eprint("[smoke] tools/call health ok")

    # ping
    r4 = rpc(p, {"jsonrpc": "2.0", "id": 4, "method": "ping", "params": {}}, timeout_s=10.0)
    eprint("[smoke] ping ok")

    # Print the JSON-RPC results to stdout (optional visibility)
    # (This stays JSON-only lines.)
    print(json.dumps(r1, ensure_ascii=False))
    print(json.dumps(r2, ensure_ascii=False))
    print(json.dumps(r3, ensure_ascii=False))
    print(json.dumps(r4, ensure_ascii=False))
    sys.stdout.flush()

    try:
        p.stdin.close()
    except Exception:
        pass

    try:
        p.terminate()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        eprint("[smoke] FAIL:", str(exc))
        raise
