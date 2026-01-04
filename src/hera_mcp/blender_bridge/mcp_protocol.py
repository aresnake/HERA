"""
Minimal JSON-RPC helpers for MCP stdio server.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def make_jsonrpc_response(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_error_response(request_id: Any, *, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}
