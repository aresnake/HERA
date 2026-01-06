from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


JSON = Dict[str, Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: JSON


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self._handlers: Dict[str, Any] = {}

    def register(self, spec: ToolSpec, handler) -> None:
        self._tools[spec.name] = spec
        self._handlers[spec.name] = handler

    def list_specs(self) -> List[JSON]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    def call(self, name: str, arguments: Optional[JSON]) -> Any:
        if name not in self._handlers:
            raise MCPError(code="tool_not_found", message=f"Unknown tool: {name}")
        return self._handlers[name](arguments or {})


class MCPError(RuntimeError):
    def __init__(self, code: str, message: str, data: Optional[JSON] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}


def _write(msg: JSON) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _err_to_json(exc: BaseException) -> JSON:
    if isinstance(exc, MCPError):
        return {
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        }
    return {
        "code": "internal_error",
        "message": str(exc),
        "data": {
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(limit=20),
        },
    }


def _make_registry() -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(
        ToolSpec(
            name="hera.ping",
            description="Health check tool; returns pong.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        lambda args: {"pong": True},
    )

    reg.register(
        ToolSpec(
            name="hera.echo",
            description="Echo back the provided payload.",
            input_schema={
                "type": "object",
                "properties": {
                    "value": {},
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        ),
        lambda args: {"value": args.get("value")},
    )

    # Intentional error tool for testing error normalization
    def _fail(_args: JSON) -> Any:
        raise MCPError(code="forced_error", message="This is an intentional test error.")

    reg.register(
        ToolSpec(
            name="hera.fail",
            description="Always fails with a normalized MCP error.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        _fail,
    )

    return reg


def handle_request(req: JSON, reg: ToolRegistry) -> Optional[JSON]:
    # Minimal JSON-RPC 2.0
    if req.get("jsonrpc") != "2.0":
        raise MCPError(code="invalid_request", message="jsonrpc must be '2.0'")

    req_id = req.get("id", None)
    method = req.get("method")

    # Notifications: id may be omitted
    def result(payload: Any) -> Optional[JSON]:
        if req_id is None:
            return None
        return {"jsonrpc": "2.0", "id": req_id, "result": payload}

    if method == "initialize":
        params = req.get("params") or {}
        # Keep this minimal; versioning can evolve later.
        return result(
            {
                "protocolVersion": "0.1",
                "serverInfo": {"name": "hera-mcp", "version": "0.0.1"},
                "capabilities": {
                    "tools": True,
                },
                "client": params.get("clientInfo", {}),
            }
        )

    if method == "tools/list":
        return result({"tools": reg.list_specs()})

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            raise MCPError(code="invalid_params", message="tools/call requires params.name (string)")
        out = reg.call(name=name, arguments=arguments)
        return result({"content": [{"type": "json", "json": out}]})

    raise MCPError(code="method_not_found", message=f"Unknown method: {method}")


def main() -> None:
    reg = _make_registry()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req, reg)
            if resp is not None:
                _write(resp)
        except BaseException as exc:
            err = _err_to_json(exc)
            # If request id is recoverable, include it; otherwise null
            try:
                req_id = None
                if isinstance(req, dict):
                    req_id = req.get("id", None)
            except Exception:
                req_id = None
            _write({"jsonrpc": "2.0", "id": req_id, "error": err})


if __name__ == "__main__":
    main()
