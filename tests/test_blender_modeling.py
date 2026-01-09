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

    ready = (tmp_dir / "pytest_modeling_worker_ready.json").resolve()
    outp = (tmp_dir / "pytest_modeling_worker_out.txt").resolve()
    errp = (tmp_dir / "pytest_modeling_worker_err.txt").resolve()

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


def test_blender_modeling_sequence():
    try:
        p, info = _start_worker()
    except RuntimeError:
        pytest.skip("Blender not available")

    try:
        env = os.environ.copy()
        env["HERA_BLENDER_PORT"] = str(info["port"])

        create_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "hera.blender.mesh.create_cube",
                    "arguments": {"name": "A", "size": 2.0, "location": [0, 0, 0]},
                },
            },
            env=env,
        )
        create_json = _content_json(create_resp)
        assert create_json.get("name") == "A"
        assert create_json.get("created") is True

        exists_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "hera.blender.object.exists", "arguments": {"name": "A"}},
            },
            env=env,
        )
        exists_json = _content_json(exists_resp)
        assert exists_json.get("exists") is True

        set_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "hera.blender.object.set_transform",
                    "arguments": {"name": "A", "location": [1, 2, 3]},
                },
            },
            env=env,
        )
        set_json = _content_json(set_resp)
        assert set_json.get("location") == [1.0, 2.0, 3.0]

        loc_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "hera.blender.object.get_location", "arguments": {"name": "A"}},
            },
            env=env,
        )
        loc_json = _content_json(loc_resp)
        assert loc_json.get("location") == [1.0, 2.0, 3.0]

        rename_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "hera.blender.object.rename", "arguments": {"from": "A", "to": "B"}},
            },
            env=env,
        )
        rename_json = _content_json(rename_resp)
        assert rename_json.get("from") == "A"
        assert rename_json.get("to") == "B"

        delete_resp = _run(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "hera.blender.object.delete", "arguments": {"name": "B"}},
            },
            env=env,
        )
        delete_json = _content_json(delete_resp)
        assert delete_json.get("deleted") is True
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
