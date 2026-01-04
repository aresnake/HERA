# tools/stdio_filter.py
# Filter non-JSON noise from Blender stdout so MCP hosts (Claude Desktop) only see JSON-RPC.
from __future__ import annotations

import os
import sys
import threading
import subprocess
from pathlib import Path


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    blender_exe = os.environ.get("BLENDER_EXE", "").strip()

    if not blender_exe:
        # fallback paths
        candidates = [
            r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
            r"D:\Blender_5.0.0_Portable\blender.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                blender_exe = c
                break

    if not blender_exe or not Path(blender_exe).exists():
        eprint(f"[hera-stdio-filter] ERROR: BLENDER_EXE not found: {blender_exe!r}")
        return 1

    # Run the real blender stdio server script (which injects src/ into sys.path)
    run_script = repo_root / "tools" / "run_stdio_blender.py"
    if not run_script.exists():
        eprint(f"[hera-stdio-filter] ERROR: missing {run_script}")
        return 1

    cmd = [blender_exe, "-b", "--factory-startup", "--python", str(run_script)]
    eprint("[hera-stdio-filter] launching:", " ".join(f'"{x}"' if " " in x else x for x in cmd))

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,          # line-buffered
        text=True,          # decode to str
        universal_newlines=True,
    )

    assert p.stdin and p.stdout and p.stderr

    stop = threading.Event()

    def pump_stdin():
        try:
            for line in sys.stdin:
                if stop.is_set():
                    break
                p.stdin.write(line)
                p.stdin.flush()
        except Exception as exc:
            eprint("[hera-stdio-filter] stdin pump error:", repr(exc))
        finally:
            try:
                p.stdin.close()
            except Exception:
                pass

    def pump_stderr():
        try:
            for line in p.stderr:
                if stop.is_set():
                    break
                # Keep all Blender stderr visible for debugging (doesn't break MCP)
                sys.stderr.write(line)
                sys.stderr.flush()
        except Exception as exc:
            eprint("[hera-stdio-filter] stderr pump error:", repr(exc))

    def pump_stdout_filtered():
        try:
            for line in p.stdout:
                if stop.is_set():
                    break
                # Only forward JSON lines to stdout. Everything else goes to stderr.
                s = line.lstrip()
                if s.startswith("{") or s.startswith("["):
                    sys.stdout.write(line)
                    sys.stdout.flush()
                else:
                    sys.stderr.write(line)
                    sys.stderr.flush()
        except Exception as exc:
            eprint("[hera-stdio-filter] stdout pump error:", repr(exc))

    t_in = threading.Thread(target=pump_stdin, daemon=True)
    t_err = threading.Thread(target=pump_stderr, daemon=True)
    t_out = threading.Thread(target=pump_stdout_filtered, daemon=True)
    t_in.start()
    t_err.start()
    t_out.start()

    rc = p.wait()
    stop.set()
    eprint(f"[hera-stdio-filter] Blender exited (code={rc})")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
