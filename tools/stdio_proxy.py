from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from typing import List


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def is_json_rpc_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if not (s.startswith("{") and s.endswith("}")):
        return False
    try:
        obj = json.loads(s)
    except Exception:
        return False
    return isinstance(obj, dict) and ("jsonrpc" in obj)


def main(argv: List[str]) -> int:
    """
    StdIO proxy:
      - Launches child command (Blender)
      - Forwards stdin to child unchanged
      - Filters child's stdout: ONLY JSON-RPC lines go to our stdout
      - Sends any non-JSON stdout noise to stderr
      - Forwards child's stderr to stderr (prefixed)
    Accepts:
      stdio_proxy.py -- <cmd...>
      stdio_proxy.py <cmd...>        (no -- required)
    """
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run (optionally preceded by --)")
    ns = parser.parse_args(argv)

    cmd = list(ns.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        eprint("stdio_proxy.py: error: missing child command. Usage: stdio_proxy.py -- <cmd...>")
        return 2

    eprint(f"[hera-stdio-proxy] launching child: {' '.join(cmd)}")

    # Launch child: inherit stdin (interactive), capture stdout/stderr
    try:
        p = subprocess.Popen(
            cmd,
            stdin=sys.stdin.buffer,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except Exception as exc:
        eprint(f"[hera-stdio-proxy] failed to start child: {exc}")
        return 1

    def pump_stdout():
        assert p.stdout is not None
        for raw in iter(p.stdout.readline, b""):
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:
                line = raw.decode(errors="replace")
            if is_json_rpc_line(line):
                # STRICT: stdout only JSON-RPC
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                # Anything else is noise -> stderr
                s = line.rstrip("\r\n")
                if s:
                    eprint("[child-stdout] " + s)

    def pump_stderr():
        assert p.stderr is not None
        for raw in iter(p.stderr.readline, b""):
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:
                line = raw.decode(errors="replace")
            s = line.rstrip("\r\n")
            if s:
                eprint("[child-stderr] " + s)

    t1 = threading.Thread(target=pump_stdout, daemon=True)
    t2 = threading.Thread(target=pump_stderr, daemon=True)
    t1.start()
    t2.start()

    try:
        return p.wait()
    except KeyboardInterrupt:
        eprint("[hera-stdio-proxy] ctrl-c: terminating child...")
        try:
            p.terminate()
        except Exception:
            pass
        try:
            return p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
            return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
