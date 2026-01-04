"""
Operation polling and cancel tools.
"""

from __future__ import annotations

from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core.queue import operation_manager
from hera_mcp.core.safe_exec import safe_execute


def _scene_state_provider() -> Dict[str, Any]:
    return scene_state.snapshot().get("scene_state", {})


def tool_ops_status(operation_id: str) -> Dict[str, Any]:
    def _op():
        record = operation_manager.get(operation_id)
        if not record:
            return {
                "status": "error",
                "error": {
                    "code": "not_found",
                    "message": f"Operation not found: {operation_id}",
                    "recoverable": False,
                },
            }
        return {
            "status": "success",
            "data": {
                "operation_id": operation_id,
                "kind": record.kind,
                "state": record.status,
                "result": record.result,
                "error": record.error,
                "cancel_requested": record.cancel_requested,
            },
            "scene_state": {**(_scene_state_provider() or {}), "ok": True},
        }

    return safe_execute("hera.ops.status", _op, _scene_state_provider)


def tool_ops_cancel(operation_id: str) -> Dict[str, Any]:
    def _op():
        ok = operation_manager.request_cancel(operation_id)
        if not ok:
            return {
                "status": "error",
                "error": {
                    "code": "not_found",
                    "message": f"Operation not found: {operation_id}",
                    "recoverable": False,
                },
            }
        record = operation_manager.get(operation_id)
        return {
            "status": "success",
            "data": {
                "operation_id": operation_id,
                "state": record.status if record else "canceled",
                "cancel_requested": True,
            },
            "scene_state": {**(_scene_state_provider() or {}), "ok": True},
        }

    return safe_execute("hera.ops.cancel", _op, _scene_state_provider)
