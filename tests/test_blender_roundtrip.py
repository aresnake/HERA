import json
import os
import subprocess
import time
from pathlib import Path

from hera_mcp.tools.blender_client import wait_worker, call_tool

ROOT = Path(__file__).resolve().parents[1]


def _pick_blender() -> str:
    paths = [
        os.environ.get("BLENDER_EXE"),
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"D:\Blender_5.0.0_Portable\blender.exe",
    ]
    for p in paths:
        if p and Path(p).exists():
            return str(Path(p).resolve())
    raise RuntimeError("No Blender found. Set BLENDER_EXE.")


def _tail(path: Path, limit_lines: int = 120) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-limit_lines:])
    except Exception as exc:
        return f"<failed reading {path}: {exc!r}>"


def _wait_ready_file(p: subprocess.Popen, ready: Path, timeout_s: float = 60.0) -> dict:
    t0 = time.time()
    while True:
        if ready.exists():
            return json.loads(ready.read_text(encoding="utf-8", errors="replace"))

        rc = p.poll()
        if rc is not None:
            raise RuntimeError(f"worker exited early rc={rc}")

        if time.time() - t0 > timeout_s:
            raise TimeoutError("ready-file not created within timeout")

        time.sleep(0.2)


def test_blender_worker_roundtrip():
    blender = _pick_blender()
    worker_py = (ROOT / "tools" / "blender_worker.py").resolve()
    assert worker_py.exists(), f"missing worker script: {worker_py}"

    tmp_dir = (ROOT / ".tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ready = (tmp_dir / "pytest_worker_ready.json").resolve()
    outp = (tmp_dir / "pytest_worker_out.txt").resolve()
    errp = (tmp_dir / "pytest_worker_err.txt").resolve()

    for p in (ready, outp, errp):
        if p.exists():
            p.unlink()

    cmd = [
        blender,
        "-b",
        "--factory-startup",
        "--disable-autoexec",
        "--python",
        str(worker_py),
        "--",
        "--port",
        "0",
        "--ready-file",
        str(ready),
    ]

    p = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=open(outp, "w", encoding="utf-8", errors="replace"),
        stderr=open(errp, "w", encoding="utf-8", errors="replace"),
        text=True,
    )

    try:
        info = _wait_ready_file(p, ready, timeout_s=60.0)
        os.environ["HERA_BLENDER_PORT"] = str(info["port"])

        wait_worker(timeout_s=30.0)

        r = call_tool("ping", {})
        assert r["ok"] is True

    except Exception as exc:
        # kill and dump logs for diagnosis
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

        raise RuntimeError(
            "pytest worker failed\n"
            f"cmd={' '.join(cmd)}\n"
            f"ready_path={ready}\n"
            f"out_tail=\n{_tail(outp)}\n"
            f"err_tail=\n{_tail(errp)}\n"
        ) from exc

    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
