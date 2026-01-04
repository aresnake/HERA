"""
Minimal MCP stdio server runnable inside Blender.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from hera_mcp.blender_bridge import scene_state
from hera_mcp.core import envelope


def _safe_scene_state() -> Dict[str, Any]:
    try:
        return scene_state.snapshot().get("scene_state", {})
    except Exception:
        return {"objects": [], "metadata": {"warning": "scene unavailable"}}


def _tool(operation: str):
    if operation == "health":
        from hera_mcp.tools.core import health

        return health.run
    if operation == "scene.snapshot":
        from hera_mcp.tools.scene import snapshot

        return snapshot.run
    if operation == "scene.create_object":
        from hera_mcp.tools.scene import create_object

        return create_object.run
    if operation == "scene.move_object":
        from hera_mcp.tools.scene import move_object

        return move_object.run
    return None


def dispatch(message: Dict[str, Any]) -> Dict[str, Any]:
    operation = message.get("operation") or message.get("op") or "unknown"
    params = message.get("params") or {}
    handler = _tool(operation)
    if not handler:
        return envelope.build_envelope(
            operation=operation,
            status="error",
            scene_state=_safe_scene_state(),
            error=envelope.build_error(
                "unknown_operation",
                f"Unsupported operation: {operation}",
                recoverable=False,
            ),
        )
    return handler(params=params)


def main() -> None:
    """
    Blocking stdio loop reading JSON lines and emitting envelopes.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = envelope.build_envelope(
                operation="unknown",
                status="error",
                scene_state=_safe_scene_state(),
                error=envelope.build_error("invalid_json", str(exc), recoverable=False),
            )
        else:
            response = dispatch(message)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
