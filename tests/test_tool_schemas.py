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

    ready = (tmp_dir / "pytest_schema_worker_ready.json").resolve()
    outp = (tmp_dir / "pytest_schema_worker_out.txt").resolve()
    errp = (tmp_dir / "pytest_schema_worker_err.txt").resolve()

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


def _validate(schema, data, path="$"):
    if not isinstance(schema, dict):
        raise AssertionError(f"{path}: schema is not an object")

    if "enum" in schema:
        if data not in schema["enum"]:
            raise AssertionError(f"{path}: {data!r} not in enum")

    schema_type = schema.get("type")
    if schema_type is not None:
        allowed = schema_type if isinstance(schema_type, list) else [schema_type]
        if not _matches_type(allowed, data):
            raise AssertionError(f"{path}: type mismatch, expected {allowed}, got {type(data).__name__}")

    if schema.get("type") == "object":
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        additional = schema.get("additionalProperties", True)
        for key in required:
            if key not in data:
                raise AssertionError(f"{path}: missing required property {key!r}")
        for key, value in data.items():
            if key in props:
                _validate(props[key], value, f"{path}.{key}")
            elif additional is False:
                raise AssertionError(f"{path}: unexpected property {key!r}")

    if schema.get("type") == "array":
        if "minItems" in schema and len(data) < schema["minItems"]:
            raise AssertionError(f"{path}: expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            raise AssertionError(f"{path}: expected at most {schema['maxItems']} items")
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for i, item in enumerate(data):
                _validate(items_schema, item, f"{path}[{i}]")


def _matches_type(allowed, data):
    for t in allowed:
        if t == "object" and isinstance(data, dict):
            return True
        if t == "array" and isinstance(data, list):
            return True
        if t == "string" and isinstance(data, str):
            return True
        if t == "number" and isinstance(data, (int, float)) and not isinstance(data, bool):
            return True
        if t == "integer" and isinstance(data, int) and not isinstance(data, bool):
            return True
        if t == "boolean" and isinstance(data, bool):
            return True
        if t == "null" and data is None:
            return True
    return False


def test_tool_schema_registry_and_validation():
    list_resp = _run({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in list_resp["result"]["tools"]]

    desc_resp = _run(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "hera.meta.tools.describe", "arguments": {}}}
    )
    desc_payload = _content_json(desc_resp)
    schema_map = {entry["name"]: entry for entry in desc_payload}

    for name in names:
        assert name in schema_map, f"missing schema for tool {name}"

    ping_resp = _run({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.ping", "arguments": {}}})
    ping_payload = _content_json(ping_resp)
    _validate(schema_map["hera.ping"]["output_schema"], ping_payload)

    _validate(schema_map["hera.meta.tools.describe"]["output_schema"], desc_payload)

    try:
        p, info = _start_worker()
    except RuntimeError:
        return

    try:
        env = os.environ.copy()
        env["HERA_BLENDER_PORT"] = str(info["port"])
        ver_resp = _run(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "hera.blender.version", "arguments": {}}},
            env=env,
        )
        ver_payload = _content_json(ver_resp)
        _validate(schema_map["hera.blender.version"]["output_schema"], ver_payload)
    finally:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
