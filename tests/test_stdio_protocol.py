from __future__ import annotations

import json
from typing import Any, Dict

from hera_mcp.blender_bridge.mcp_stdio import MCPStdioServer


def send(server: MCPStdioServer, payload: Dict[str, Any]) -> Dict[str, Any]:
    return server.handle_request(payload)


def test_initialize_and_list_and_call(monkeypatch):
    # Provide a stub bpy module to avoid Blender dependency during protocol tests.
    class DummyObject:
        def __init__(self, name: str, type_name: str = "MESH"):
            self.name = name
            self.type = type_name
            self.location = [0.0, 0.0, 0.0]

    class DummyMesh:
        def __init__(self, name: str):
            self.name = name
            self.type = "MESH"

        def from_pydata(self, *args, **kwargs):
            return None

        def update(self):
            return None

    class DummyMeshes:
        def new(self, name: str):
            return DummyMesh(name)

    class DummyLight:
        def __init__(self, name: str, type_name: str):
            self.name = name
            self.type = type_name

    class DummyLights:
        def new(self, name: str, type: str = "POINT"):
            return DummyLight(name, type)

    class DummyCamera:
        def __init__(self, name: str):
            self.name = name
            self.type = "CAMERA"

    class DummyCameras:
        def new(self, name: str):
            return DummyCamera(name)

    class DummyObjects:
        def __init__(self, store):
            self.store = store

        def new(self, name: str, data):
            obj_type = getattr(data, "type", "MESH")
            obj = DummyObject(name, obj_type)
            self.store[name] = obj
            return obj

        def get(self, name: str):
            return self.store.get(name)

    class DummyCollectionObjects:
        def __init__(self, store):
            self.store = store

        def link(self, obj):
            # Already stored by DummyObjects.new
            self.store[obj.name] = obj

    class DummyCollection:
        def __init__(self, store):
            self.objects = DummyCollectionObjects(store)

    class DummyScene:
        name = "Scene"

        def __init__(self, store):
            self._store = store
            self.collection = DummyCollection(store)

        @property
        def objects(self):
            return list(self._store.values())

    class DummyData:
        def __init__(self, store, count: int):
            self.meshes = DummyMeshes()
            self.lights = DummyLights()
            self.cameras = DummyCameras()
            self.objects = DummyObjects(store)
            self.scenes = [DummyScene(store) for _ in range(1)]
            # preload objects
            for i in range(count):
                self.objects.new(f"obj{i}", DummyMesh(f"mesh{i}"))

    class DummyContext:
        def __init__(self, store):
            self.scene = DummyScene(store)

    class DummyBpy:
        def __init__(self, count: int):
            self._store = {}
            self.data = DummyData(self._store, count)
            self.context = DummyContext(self._store)

    # Inject dummy bpy with >100 objects to hit chunking.
    import sys

    sys.modules["bpy"] = DummyBpy(150)

    server = MCPStdioServer()

    init_resp = send(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "hera-mcp"

    list_resp = send(server, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = list_resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert {"hera.health", "hera.scene.snapshot", "hera.scene.snapshot_chunk", "hera.ops.resume"}.issubset(
        tool_names
    )

    # health call
    call_resp = send(
        server,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hera.health", "arguments": {}}},
    )
    assert call_resp["result"]["isError"] is False
    content = call_resp["result"]["content"][0]["text"]
    envelope = json.loads(content)
    assert envelope.get("status") in ("ok", "success", "partial", "chunked")
    assert "scene_state" in envelope

    # snapshot coercion and chunking
    snap_resp = send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "hera.scene.snapshot", "arguments": {"limit_objects": "50", "offset": "0"}},
        },
    )
    snap_content = json.loads(snap_resp["result"]["content"][0]["text"])
    assert snap_content["status"] == "chunked"
    next_token = snap_content["data"]["next_token"]
    assert next_token

    # snapshot chunk continuation
    chunk_resp = send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "hera.scene.snapshot_chunk", "arguments": {"token": next_token}},
        },
    )
    chunk_content = json.loads(chunk_resp["result"]["content"][0]["text"])
    assert "objects" in chunk_content["data"]

    # type coercion for create/move (location passed as tuple of strings)
    create_resp = send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "hera.scene.create_object",
                "arguments": {"name": "CubeX", "location": ("1", "2", "3")},
            },
        },
    )
    assert create_resp["result"]["isError"] is False

    move_resp = send(
        server,
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "hera.scene.move_object",
                "arguments": {"name": "CubeX", "delta": ["1", "0", "0"]},
            },
        },
    )
    assert move_resp["result"]["isError"] is False
