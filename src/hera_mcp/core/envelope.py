"""
Envelope builders and chunking helpers for HERA MCP.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_CHUNK_SIZE = 100


def _now_ms() -> int:
    return int(time.perf_counter() * 1000)


def build_error(
    code: str,
    message: str,
    recoverable: bool = True,
    retry_after_ms: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }
    if retry_after_ms is not None:
        error["retry_after_ms"] = retry_after_ms
    if details:
        error["details"] = details
    return error


def build_diff(
    created: Optional[List[Any]] = None,
    modified: Optional[List[Any]] = None,
    deleted: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    if created:
        diff["created"] = created
    if modified:
        diff["modified"] = modified
    if deleted:
        diff["deleted"] = deleted
    return diff


def chunk_list(
    items: Iterable[Any],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    offset: int = 0,
) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
    """
    Chunk a list-like iterable. Returns (chunk, resume_token).
    """
    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE
    items_list = list(items)
    end = offset + chunk_size
    chunk = items_list[offset:end]
    resume_token = None
    if end < len(items_list):
        resume_token = {"offset": end, "total": len(items_list)}
    return chunk, resume_token


def build_envelope(
    *,
    operation: str,
    status: str = "ok",
    data: Optional[Dict[str, Any]] = None,
    data_diff: Optional[Dict[str, Any]] = None,
    scene_state: Optional[Dict[str, Any]] = None,
    next_actions: Optional[List[str]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
    resume_token: Optional[Dict[str, Any]] = None,
    started_ms: Optional[int] = None,
) -> Dict[str, Any]:
    envelope: Dict[str, Any] = {
        "status": status,
        "operation": operation,
        "scene_state": scene_state or {},
    }
    if data is not None:
        envelope["data"] = data
    if data_diff:
        envelope["data_diff"] = data_diff
    if next_actions:
        envelope["next_actions"] = next_actions
    if resume_token is not None:
        envelope["resume_token"] = resume_token

    if started_ms is not None:
        duration_ms = max(0, _now_ms() - started_ms)
        metrics = {"duration_ms": duration_ms, **(metrics or {})}
    if metrics:
        envelope["metrics"] = metrics

    if error:
        envelope["error"] = error
    return envelope
