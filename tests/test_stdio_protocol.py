from __future__ import annotations

import json
from typing import Any, Dict

from hera_mcp.blender_bridge.mcp_stdio import MCPStdioServer


def send(server: MCPStdioServer, payload: Dict[str, Any]) -> Dict[str, Any]:
    return server.handle_request(payload)


def test_initialize_and_list_and_call(monkeypatch):
    # Provide a stub bpy module to avoid Blender dependency during protocol tests.
    class DummyObject:
        name = "stub"
        type = "MESH"

        def __init__(self):
            self.location = (0.0, 0.0, 0.0)

    class DummyScene:
        name = "Scene"

        def __init__(self):
            self.objects = [DummyObject()]

    class DummyData:
        scenes = [DummyScene()]

    class DummyContext:
        scene = DummyScene()

    class DummyBpy:
        data = DummyData()
        context = DummyContext()

    # Inject dummy bpy
    import sys

    sys.modules["bpy"] = DummyBpy()

    server = MCPStdioServer()

    init_resp = send(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "hera-mcp"

    list_resp = send(server, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = list_resp["result"]["tools"]
    assert any(t["name"] == "hera.health" for t in tools)

    call_resp = send(
        server,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.health", "arguments": {}}},
    )
    assert call_resp["result"]["isError"] is False
    content = call_resp["result"]["content"][0]["text"]
    envelope = json.loads(content)
    assert envelope.get("status") in ("ok", "success", "partial")
    assert "scene_state" in envelope
