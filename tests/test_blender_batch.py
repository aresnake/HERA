import json
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(req, env=None):
    p = subprocess.Popen(
        [os.sys.executable, "-m", "hera_mcp.server.stdio"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        p.stdin.write(json.dumps(req) + "\n")
        p.stdin.flush()
        line = p.stdout.readline().strip()
        assert line, "no response"
        return json.loads(line)
    finally:
        p.kill()


def _content_json(resp):
    return resp["result"]["content"][0]["json"]


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


def _start_worker():
    blender = _pick_blender()
    worker_py = (ROOT / "tools" / "blender_worker.py").resolve()
    tmp_dir = (ROOT / ".tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ready = (tmp_dir / "pytest_batch_worker_ready.json").resolve()
    outp = (tmp_dir / "pytest_batch_worker_out.txt").resolve()
    errp = (tmp_dir / "pytest_batch_worker_err.txt").resolve()

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

    info = _wait_ready_file(p, ready, timeout_s=60.0)
    return p, info


def test_blender_batch_roundtrip():
    try:
        p, info = _start_worker()
    except RuntimeError:
        pytest.skip("Blender not available")

    try:
        env = os.environ.copy()
        env["HERA_BLENDER_PORT"] = str(info["port"])

        batch_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "hera.blender.batch",
                    "arguments": {
                        "steps": [
                            {"tool": "hera.blender.scene.list_objects", "args": {}},
                            {"tool": "hera.blender.object.move", "args": {"name": "Cube", "location": [1, 2, 3]}},
                            {"tool": "hera.blender.object.get_location", "args": {"name": "Cube"}},
                        ]
                    },
                },
            },
            env=env,
        )
        payload = _content_json(batch_resp)
        results = payload.get("results") or []
        assert len(results) == 3, batch_resp
        assert all(r.get("ok") is True for r in results), batch_resp

        move_loc = results[1]["result"]["location"]
        assert move_loc == [1.0, 2.0, 3.0]

        loc = results[2]["result"]["location"]
        assert abs(loc[0] - 1.0) < 1e-4
        assert abs(loc[1] - 2.0) < 1e-4
        assert abs(loc[2] - 3.0) < 1e-4
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
