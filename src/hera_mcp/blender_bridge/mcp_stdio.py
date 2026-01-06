"""
MCP-compatible JSON-RPC stdio server for Blender/headless.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from hera_mcp.blender_bridge import scene_state
from hera_mcp.blender_bridge.mcp_protocol import (
    make_error_response,
    make_jsonrpc_response,
)
from hera_mcp.core import coerce, envelope


def _safe_scene_state() -> Dict[str, Any]:
    try:
        return scene_state.snapshot().get("scene_state", {})
    except Exception:
        return {"objects": [], "metadata": {"warning": "scene unavailable"}}


def log_err(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def _tool_callable(name: str):
    if name == "hera.health":
        from hera_mcp.tools.core.health import tool_health
        return tool_health

    if name == "hera.scene.snapshot":
        from hera_mcp.tools.scene.snapshot import tool_scene_snapshot
        return tool_scene_snapshot

    if name == "hera.scene.snapshot_chunk":
        from hera_mcp.tools.scene.snapshot import tool_scene_snapshot_chunk
        return tool_scene_snapshot_chunk

    if name == "hera.scene.create_object":
        from hera_mcp.tools.scene.create_object import tool_create_object
        return tool_create_object

    if name == "hera.scene.move_object":
        from hera_mcp.tools.scene.move_object import tool_move_object
        return tool_move_object

    if name == "hera.object.get":
        from hera_mcp.tools.scene.get_object import tool_get_object
        
from hera_mcp.tools.scene.set_transform import tool_set_transform
return tool_get_object

    if name == "hera.object.set_transform":
        obj_name = str(args.get("name", ""))
        location = args.get("location", None)
        rotation_euler = args.get("rotation_euler", None)
        scale = args.get("scale", None)
        return tool_set_transform(
            name=obj_name,
            location=location,
            rotation_euler=rotation_euler,
            scale=scale,
        )
    if name == "hera.ops.status":
        from hera_mcp.tools.core.ops import tool_ops_status
        return tool_ops_status

    if name == "hera.ops.cancel":
        from hera_mcp.tools.core.ops import tool_ops_cancel
        return tool_ops_cancel

    if name == "hera.ops.resume":
        from hera_mcp.tools.core.ops import tool_ops_resume
        return tool_ops_resume

    return None


def _tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "name": "hera.health",
            "description": "Healthcheck returning a scene snapshot summary.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "hera.scene.snapshot",
            "description": "Snapshot the scene objects with chunking support.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit_objects": {
                        "type": "integer",
                        "description": "Maximum objects to include.",
                        "default": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Start offset for chunking.",
                        "default": 0,
                    },
                },
            },
        },
        {
            "name": "hera.scene.snapshot_chunk",
            "description": "Fetch the next chunk using a stateless token.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "token": {
                        "type": "string",
                        "description": "Chunk token from previous snapshot.",
                    }
                },
            },
        },
        {
            "name": "hera.scene.create_object",
            "description": "Create a cube, sphere, camera, or light (data-first).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "default": "CUBE"},
                    "name": {"type": "string", "default": "Object"},
                    "location": {
                        "type": "array",
                        "description": "XYZ coordinates",
                        "default": [0, 0, 0],
                    },
                    "light_type": {"type": "string", "default": "POINT"},
                },
            },
        },
        {
            "name": "hera.scene.move_object",
            "description": "Move an existing object by delta or absolute location.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Object name to move"},
                    "location": {"type": "array", "description": "Absolute location"},
                    "delta": {"type": "array", "description": "Delta translation"},
                },
            },
        },
        {
            "name": "hera.object.get",
            "description": "Inspect an object (type/location/rotation/scale).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Object name to inspect"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "hera.ops.status",
            "description": "Check status of a long-running operation.",
            "inputSchema": {
                "type": "object",
                "properties": {"operation_id": {"type": "string", "description": "Operation id"}},
            },
        },
        {
            "name": "hera.ops.cancel",
            "description": "Request cancellation of a long-running operation.",
            "inputSchema": {
                "type": "object",
                "properties": {"operation_id": {"type": "string", "description": "Operation id"}},
            },
        },
        {
            "name": "hera.ops.resume",
            "description": "Resume a partial operation using a resume_token.",
            "inputSchema": {
                "type": "object",
                "properties": {"resume_token": {"type": "string", "description": "Opaque resume token"}},
            },
        },
    ]


class MCPStdioServer:
    def __init__(self) -> None:
        self._tools = _tool_definitions()
        self._shutdown = False
        self._exit = False

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any | None]:
        try:
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params")
            keys = list(params.keys()) if isinstance(params, dict) else type(params)
            log_err(f"[mcp] <- method={method} id={request_id} keys={keys}")

            if method == "notifications/initialized":
                return None

            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "hera-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                }
                return make_jsonrpc_response(request_id, result)

            if method == "ping":
                return make_jsonrpc_response(request_id, {"ok": True})

            if method == "tools/list":
                return make_jsonrpc_response(request_id, {"tools": self._tools})

            if method == "tools/call":
                params = params or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                log_err(
                    f"[mcp] tools/call name={name} arg_keys={list(arguments.keys()) if isinstance(arguments, dict) else type(arguments)}"
                )
                return self._handle_tool_call(request_id, name, arguments)

            if method == "resources/list":
                return make_jsonrpc_response(request_id, {"resources": []})

            if method == "prompts/list":
                return make_jsonrpc_response(request_id, {"prompts": []})

            if method == "shutdown":
                self._shutdown = True
                return make_jsonrpc_response(request_id, {"ok": True})

            if method == "exit":
                self._exit = True
                return make_jsonrpc_response(request_id, {}) if request_id is not None else None

            log_err(f"[mcp] unknown method: {method}")
            return make_error_response(request_id, code=-32601, message="Method not found")
        except Exception as exc:  # pragma: no cover
            log_err(f"handle_request error: {exc}")
            err_payload = envelope.build_error(code="internal_error", message=str(exc), recoverable=False)
            return make_jsonrpc_response(
                request.get("id"),
                {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": f"Error: {exc}"},
                        {"type": "text", "text": json.dumps(err_payload)},
                    ],
                },
            )

    def _handle_tool_call(self, request_id: Any, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not name:
            return make_error_response(request_id, code=-32602, message="Tool name missing")

        tool_fn = _tool_callable(name)
        if not tool_fn:
            err = envelope.build_error("unknown_tool", f"Unsupported tool: {name}", recoverable=False)
            return make_jsonrpc_response(
                request_id,
                {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": f"Error: Unsupported tool {name}"},
                        {"type": "text", "text": json.dumps(err)},
                    ],
                },
            )

        try:
            coerced_args = self._coerce_arguments(name, arguments)
            result = tool_fn(**coerced_args) if coerced_args else tool_fn()
        except Exception as exc:  # pragma: no cover
            log_err(f"tool_call error for {name}: {exc}")
            err = envelope.build_error("tool_failure", str(exc), recoverable=False)
            return make_jsonrpc_response(
                request_id,
                {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": f"Error: {exc}"},
                        {"type": "text", "text": json.dumps(err)},
                    ],
                },
            )

        is_error = result.get("status") in ("error", "failed")
        payload = json.dumps(result)
        content = [{"type": "text", "text": payload}]
        if is_error:
            content = [
                {"type": "text", "text": f"Error: {result.get('error') or result.get('status')}"},
                {"type": "text", "text": payload},
            ]
        return make_jsonrpc_response(request_id, {"isError": is_error, "content": content})

    def _coerce_arguments(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        args: Dict[str, Any] = {}
        if name == "hera.scene.snapshot":
            args["limit_objects"] = int(coerce.to_float(arguments.get("limit_objects", arguments.get("limit", 100))))
            args["offset"] = int(coerce.to_float(arguments.get("offset", 0)))
        elif name == "hera.scene.snapshot_chunk":
            token = arguments.get("token") or arguments.get("resume_token") or ""
            args["token"] = str(token)
        elif name == "hera.scene.create_object":
            args["type"] = str(arguments.get("type", "CUBE"))
            args["name"] = coerce.to_name(arguments.get("name", "Object"))
            args["location"] = coerce.to_vector3(arguments.get("location"))
            args["light_type"] = str(arguments.get("light_type", "POINT"))
        elif name == "hera.scene.move_object":
            args["name"] = coerce.to_name(arguments.get("name") or arguments.get("object"))
            if "location" in arguments:
                args["location"] = coerce.to_vector3(arguments.get("location"))
            if "delta" in arguments:
                args["delta"] = coerce.to_vector3(arguments.get("delta"))
        elif name == "hera.object.get":
            args["name"] = coerce.to_name(arguments.get("name") or arguments.get("object"))
        elif name in ("hera.ops.status", "hera.ops.cancel"):
            args["operation_id"] = str(arguments.get("operation_id", ""))
        elif name == "hera.ops.resume":
            args["resume_token"] = str(arguments.get("resume_token", ""))
        else:
            args.update(arguments)
        return args


def main() -> None:
    """
    Blocking stdio loop reading JSON-RPC lines and emitting responses.
    """
    server = MCPStdioServer()
    log_err("hera-mcp stdio server starting")

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            resp = make_error_response(None, code=-32700, message="Invalid JSON")
        else:
            resp = server.handle_request(message)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        if server._exit or server._shutdown:
            break


if __name__ == "__main__":
    main()

