from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import threading
from pathlib import Path
from typing import Optional


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def is_jsonrpc(obj) -> bool:
    return isinstance(obj, dict) and ("jsonrpc" in obj)


def read_one_jsonrpc_line(p: subprocess.Popen, timeout_s: float = 8.0) -> Optional[dict]:
    """
    Read stdout until we get a valid JSON-RPC dict, skipping blank/noise lines.
    Works with both text noise and pure JSON streams.
    """
    t0 = time.time()
    buf = b""
    while time.time() - t0 < timeout_s:
        ch = p.stdout.read(1)  # type: ignore[attr-defined]
        if not ch:
            # process may still be alive; give it a moment
            if p.poll() is not None:
                return None
            time.sleep(0.01)
            continue

        buf += ch
        if ch != b"\n":
            continue

        line = buf.decode("utf-8", errors="replace").strip()
        buf = b""

        if not line:
            continue

        # Some hosts/loggers can accidentally prepend noise; ignore non-JSON lines.
        if not (line.startswith("{") and line.endswith("}")):
            continue

        try:
            obj = json.loads(line)
        except Exception:
            continue

        if is_jsonrpc(obj):
            return obj

    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    launcher = repo_root / "tools" / "hera-stdio.ps1"
    if not launcher.exists():
        print(f"[smoke-claude] launcher not found: {launcher}", file=sys.stderr)
        return 1

    # Always use pwsh if available (more predictable than legacy powershell)
    shell = "pwsh"
    try:
        subprocess.check_call([shell, "-NoLogo", "-NoProfile", "-Command", "exit 0"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        shell = "powershell"

    cmd = [shell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher)]
    print("[smoke-claude] launching:", " ".join(cmd), file=sys.stderr)

    p = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        text=False,
    )

    # Pump stderr so buffers never block
    def pump_err():
        assert p.stderr is not None
        for raw in iter(p.stderr.readline, b""):
            s = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if s:
                print("[server-stderr] " + s, file=sys.stderr)

    threading.Thread(target=pump_err, daemon=True).start()

    def rpc(req: dict, timeout_s: float = 10.0) -> dict:
        assert p.stdin is not None
        assert p.stdout is not None
        msg = (j(req) + "\n").encode("utf-8")
        p.stdin.write(msg)
        p.stdin.flush()

        obj = read_one_jsonrpc_line(p, timeout_s=timeout_s)
        if obj is None:
            raise RuntimeError("No JSON-RPC response (timeout or process exited).")
        return obj

    try:
        r1 = rpc({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "hera-smoke-claude", "version": "0.0"},
                "capabilities": {}
            }
        }, timeout_s=12.0)
        print("[smoke-claude] initialize =", j(r1), file=sys.stderr)

        # Claude peut appeler des méthodes optionnelles => on teste aussi
        r2 = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, timeout_s=12.0)
        print("[smoke-claude] tools/list =", j(r2), file=sys.stderr)

        r3 = rpc({"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}}, timeout_s=6.0)
        print("[smoke-claude] ping =", j(r3), file=sys.stderr)

        # Retry tools/call health until success (queue may delay responses during boot)
        success = False
        for attempt in range(1, 21):
            try:
                r4 = rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": 100 + attempt,
                        "method": "tools/call",
                        "params": {"name": "hera.health", "arguments": {}},
                    },
                    timeout_s=2.0,
                )
            except Exception as exc:
                time.sleep(0.25)
                continue
            result = r4.get("result", {})
            is_error = result.get("isError")
            if not is_error:
                # Validate content is a JSON string with status success
                content = result.get("content") or []
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", "")
                    try:
                        env = json.loads(text)
                        if env.get("status") == "success":
                            success = True
                            print("[smoke-claude] tools/call health =", j(r4), file=sys.stderr)
                            break
                    except Exception:
                        pass
            time.sleep(0.25)

        if not success:
            raise RuntimeError("tools/call health did not succeed after retries.")

        print("[smoke-claude] OK", file=sys.stderr)
        return 0

    except Exception as e:
        print("[smoke-claude] FAIL:", str(e), file=sys.stderr)
        return 2

    finally:
        try:
            if p.stdin:
                p.stdin.close()
        except Exception:
            pass
        try:
            p.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
