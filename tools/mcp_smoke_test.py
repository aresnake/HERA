from __future__ import annotations

import json
import os
import subprocess
import sys
import time

def j(obj): 
    return json.dumps(obj, ensure_ascii=False)

def read_one_json_line(p: subprocess.Popen, timeout_s: float = 5.0):
    # Read one JSON line from stdout with a timeout.
    t0 = time.time()
    buf = b""
    while time.time() - t0 < timeout_s:
        ch = p.stdout.read(1)
        if not ch:
            break
        buf += ch
        if ch == b"\n":
            line = buf.decode("utf-8", errors="replace").strip()
            if not line:
                buf = b""
                continue
            return line
    return None

def main() -> int:
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ps1 = os.path.join(repo, "tools", "hera-stdio.ps1")

    # IMPORTANT: run launcher via pwsh so stdio stays attached
    cmd = ["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1]

    print("[smoke] launching:", " ".join(cmd), file=sys.stderr)
    p = subprocess.Popen(
        cmd,
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        bufsize=0,
    )

    # Pump stderr in background (so buffers don't block)
    def pump_err():
        for raw in iter(p.stderr.readline, b""):
            s = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if s:
                print("[server-stderr] " + s, file=sys.stderr)

    import threading
    threading.Thread(target=pump_err, daemon=True).start()

    def rpc(req):
        msg = (j(req) + "\n").encode("utf-8")
        p.stdin.write(msg)
        p.stdin.flush()
        line = read_one_json_line(p, timeout_s=6.0)
        if not line:
            raise RuntimeError("No JSON-RPC response (timeout).")
        return json.loads(line)

    # 1) initialize (MCP hosts usually expect capabilities)
    r1 = rpc({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2024-11-05",
        "clientInfo":{"name":"hera-smoke","version":"0.0"},
        "capabilities":{}
    }})
    print("[smoke] initialize =", j(r1), file=sys.stderr)

    # 2) tools/list
    r2 = rpc({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
    print("[smoke] tools/list =", j(r2), file=sys.stderr)

    # 3) tools/call health
    r3 = rpc({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{
        "name":"hera.health","arguments":{}
    }})
    print("[smoke] tools/call health =", j(r3), file=sys.stderr)

    # If Claude expects ping, test it too
    r4 = rpc({"jsonrpc":"2.0","id":4,"method":"ping","params":{}})
    print("[smoke] ping =", j(r4), file=sys.stderr)

    # Graceful exit
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
    except Exception as e:
        print("[smoke] FAIL:", str(e), file=sys.stderr)
        raise
