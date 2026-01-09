from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Dict, Optional

from hera_mcp.tools.blender_client import call_tool, wait_worker

JSON = Dict[str, Any]


def _write(obj: JSON) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _err(req_id: Any, code: str, message: str, data: Optional[JSON] = None) -> JSON:
    e: JSON = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": e}


def _ok(req_id: Any, result: Any) -> JSON:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _tool_specs() -> list[JSON]:
    return [
        {
            "name": "hera.ping",
            "description": "Local ping (does not require Blender).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "hera.blender.version",
            "description": "Return Blender version and build info (proxy).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "hera.blender.scene.list_objects",
            "description": "List objects in the current Blender scene (proxy).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "hera.blender.object.move",
            "description": "Move a Blender object by name (proxy).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                },
                "required": ["name", "location"],
                "additionalProperties": False,
            },
        },
        {
            "name": "hera.blender.object.exists",
            "description": "Check if a Blender object exists by name (proxy).",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "hera.blender.object.get_location",
            "description": "Get a Blender object's location by name (proxy).",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "hera.blender.scene.get_active_object",
            "description": "Get the active object in Blender (proxy).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "hera.list_objects",
            "description": "List objects in the current Blender scene (proxy).",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "hera.create_cube",
            "description": "Create a cube in Blender (proxy).",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "size": {"type": "number"}},
                "additionalProperties": False,
            },
        },
        {
            "name": "hera.fail",
            "description": "Always fails (local), used to test error normalization.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]


def _call_proxy(tool_name: str, args: JSON) -> JSON:
    try:
        wait_worker(timeout_s=5.0)
        return call_tool(tool_name, args)
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "blender_unreachable",
                "message": str(exc),
                "details": {"exception": type(exc).__name__},
            },
        }


def _handle_tools_call(params: JSON) -> JSON:
    name = params.get("name")
    args = params.get("arguments") or {}

    if not isinstance(name, str) or not name:
        return {"ok": False, "error": {"code": "invalid_request", "message": "missing tool name"}}
    if not isinstance(args, dict):
        return {"ok": False, "error": {"code": "invalid_request", "message": "arguments must be an object"}}

    # ✅ Local ping (NO Blender dependency) — required by tests
    if name == "hera.ping":
        return {"ok": True, "result": {"pong": True}}

    # Local forced error (must NOT require Blender)
    if name == "hera.fail":
        return {"ok": False, "error": {"code": "forced_error", "message": "forced failure for tests"}}

    # Proxy tools
    if name == "hera.list_objects":
        return _call_proxy("list_objects", {})
    if name == "hera.create_cube":
        return _call_proxy("create_cube", args)
    if name == "hera.blender.version":
        return _call_proxy("blender.version", {})
    if name == "hera.blender.scene.list_objects":
        return _call_proxy("blender.scene.list_objects", {})
    if name == "hera.blender.object.move":
        return _call_proxy("blender.object.move", args)
    if name == "hera.blender.object.exists":
        return _call_proxy("blender.object.exists", args)
    if name == "hera.blender.object.get_location":
        return _call_proxy("blender.object.get_location", args)
    if name == "hera.blender.scene.get_active_object":
        return _call_proxy("blender.scene.get_active_object", {})

    return {"ok": False, "error": {"code": "unknown_tool", "message": f"Unknown tool: {name}"}}


def main() -> None:
    for line in sys.stdin:
        raw = (line or "").strip()
        if not raw:
            continue

        try:
            req = json.loads(raw)
        except Exception:
            _write(_err(None, "parse_error", "Invalid JSON"))
            continue

        req_id = req.get("id", None)
        method = req.get("method")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "hera-mcp", "version": "0.0.1"},
                }
                _write(_ok(req_id, result))
                continue

            if method == "tools/list":
                _write(_ok(req_id, {"tools": _tool_specs()}))
                continue

            if method == "tools/call":
                call_res = _handle_tools_call(params if isinstance(params, dict) else {})
                if call_res.get("ok") is True:
                    _write(_ok(req_id, {"content": [{"type": "text", "json": call_res.get("result", {})}]}))
                else:
                    err = call_res.get("error") or {}
                    _write(_err(req_id, err.get("code", "execution_error"), err.get("message", "error"), {"raw": err}))
                continue

            _write(_err(req_id, "method_not_found", f"Unknown method: {method}"))

        except Exception as exc:
            _write(_err(req_id, "internal_error", str(exc), {"traceback": traceback.format_exc()}))


if __name__ == "__main__":
    main()
