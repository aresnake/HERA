import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(req):
    # Run the stdio server as a module entry (script installed later)
    p = subprocess.Popen(
        [sys.executable, "-m", "hera_mcp.server.stdio"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        p.stdin.write(json.dumps(req) + "\n")
        p.stdin.flush()
        line = p.stdout.readline().strip()
        assert line, "no response"
        return json.loads(line)
    finally:
        p.kill()


def test_initialize():
    r = _run({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "pytest"}}})
    assert r["id"] == 1
    assert "result" in r
    assert r["result"]["serverInfo"]["name"] == "hera-mcp"


def test_tools_list_and_call():
    r = _run({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert "hera.blender.object.exists" in names
    assert "hera.blender.object.get_location" in names
    assert "hera.blender.scene.get_active_object" in names
    assert "hera.blender.batch" in names
    assert "hera.meta.tools.describe" in names
    assert "hera.ping" in names

    r2 = _run({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.ping", "arguments": {}}})
    assert r2["result"]["content"][0]["json"]["pong"] is True


def test_error_is_normalized():
    r = _run({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "hera.fail", "arguments": {}}})
    assert "error" in r
    assert r["error"]["code"] == "forced_error"
