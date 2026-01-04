"""
Safe execution wrapper that guarantees structured envelopes.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict

from . import envelope


def _safe_scene(scene_state_provider: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        return scene_state_provider()
    except Exception:
        return {"objects": [], "metadata": {"warning": "scene snapshot failed"}}


def safe_execute(
    operation: str,
    func: Callable[[], Dict[str, Any]],
    scene_state_provider: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Executes a tool function safely, wrapping all errors into envelopes.
    """
    started = int(time.perf_counter() * 1000)
    try:
        result = func() or {}
        metrics = result.get("metrics", {})
        duration_ms = int(time.perf_counter() * 1000) - started
        metrics = {**metrics, "duration_ms": duration_ms}
        env = envelope.build_envelope(
            operation=operation,
            status=result.get("status", "ok"),
            data=result.get("data"),
            data_diff=result.get("data_diff"),
            scene_state=result.get("scene_state") or _safe_scene(scene_state_provider),
            next_actions=result.get("next_actions"),
            metrics=metrics,
            error=result.get("error"),
            resume_token=result.get("resume_token"),
            started_ms=None,
        )
        return env
    except Exception as exc:  # pragma: no cover - defensive path
        return envelope.build_envelope(
            operation=operation,
            status="error",
            data=None,
            scene_state=_safe_scene(scene_state_provider),
            metrics={"duration_ms": int(time.perf_counter() * 1000) - started},
            error=envelope.build_error(
                code="internal_error",
                message=str(exc),
                recoverable=False,
            ),
        )
