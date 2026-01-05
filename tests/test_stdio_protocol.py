from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
PROXY = REPO_ROOT / "tools" / "stdio_proxy.py"


def spawn_proxy(child_cmd):
    proc = subprocess.Popen(
        [sys.executable, "-u", str(PROXY), "--"] + child_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    return proc


def read_json_line(proc: subprocess.Popen, timeout: float = 5.0) -> Optional[dict]:
    start = time.time()
    buf = ""
    while time.time() - start < timeout:
        if proc.stdout is None:
            return None
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except Exception:
            continue
    return None


def drain_stderr(proc: subprocess.Popen, sink: Callable[[str], None]):
    def _pump():
        if proc.stderr is None:
            return
        for line in proc.stderr:
            sink(line.rstrip("\n"))

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    return t


def test_ping_and_json_only():
    # Child: emits readiness token to stderr, then echoes a ping response and noise to stdout.
    child_code = r"""
import sys, json, time
sys.stderr.write("HERA_READY\n"); sys.stderr.flush()
for line in sys.stdin:
    obj = json.loads(line)
    if obj.get("method") == "ping":
        sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":obj.get("id"),"result":{"ok":True}})+"\n"); sys.stdout.flush()
    elif obj.get("method") == "tools/call":
        sys.stdout.write("NOISE\n"); sys.stdout.flush()
        sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":obj.get("id"),"result":{"ok":True}})+"\n"); sys.stdout.flush()
"""
    proc = spawn_proxy([sys.executable, "-u", "-c", child_code])
    logs = []
    drain_stderr(proc, logs.append)

    assert proc.stdin is not None
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n")
    proc.stdin.flush()

    resp = read_json_line(proc, timeout=5)
    assert resp and resp.get("result", {}).get("ok") is True

    # ensure no noise on stdout
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {}}) + "\n")
    proc.stdin.flush()
    resp2 = read_json_line(proc, timeout=5)
    assert resp2 and resp2.get("id") == 2
    # readiness token on stderr
    assert any("HERA_READY" in l for l in logs)
    proc.terminate()


def test_tools_call_before_ready_gets_error_on_child_exit():
    # Child never emits readiness and exits immediately.
    child_code = r"""
import sys
sys.exit(0)
"""
    proc = spawn_proxy([sys.executable, "-u", "-c", child_code])
    logs = []
    drain_stderr(proc, logs.append)
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {}}) + "\n")
    proc.stdin.flush()
    resp = read_json_line(proc, timeout=5)
    assert resp is not None
    assert resp.get("result", {}).get("isError") is True
    proc.wait(timeout=5)


def test_tools_call_after_ready_forwarded():
    child_code = r"""
import sys, json
sys.stderr.write("HERA_READY\n"); sys.stderr.flush()
for line in sys.stdin:
    obj = json.loads(line)
    if obj.get("method") == "tools/call":
        sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":obj.get("id"),"result":{"isError":False,"content":[{"type":"text","text":"ok"}]}})+"\n"); sys.stdout.flush()
"""
    proc = spawn_proxy([sys.executable, "-u", "-c", child_code])
    logs = []
    drain_stderr(proc, logs.append)
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {}}) + "\n")
    proc.stdin.flush()
    resp = read_json_line(proc, timeout=5)
    assert resp is not None
    assert resp.get("result", {}).get("isError") is False
    assert any("HERA_READY" in l for l in logs)
    proc.terminate()
