"""
Single-thread execution gate and lightweight operation tracking.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class MonoQueue:
    """
    Guards execution with a single lock to prevent concurrent Blender mutations.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        with self._lock:
            return func(*args, **kwargs)


@dataclass
class OperationRecord:
    operation_id: str
    kind: str
    status: str = "accepted"  # accepted|running|completed|failed|canceled
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cancel_requested: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class OperationManager:
    """
    Tracks operations for polling/cancelation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._operations: Dict[str, OperationRecord] = {}

    def create(self, kind: str, metadata: Optional[Dict[str, Any]] = None) -> OperationRecord:
        op_id = str(uuid.uuid4())
        record = OperationRecord(operation_id=op_id, kind=kind, metadata=metadata or {})
        with self._lock:
            self._operations[op_id] = record
        return record

    def start(self, op_id: str) -> None:
        with self._lock:
            rec = self._operations.get(op_id)
            if rec:
                rec.status = "running"

    def complete(self, op_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            rec = self._operations.get(op_id)
            if rec:
                rec.status = "completed"
                rec.result = result

    def fail(self, op_id: str, error: str) -> None:
        with self._lock:
            rec = self._operations.get(op_id)
            if rec:
                rec.status = "failed"
                rec.error = error

    def request_cancel(self, op_id: str) -> bool:
        with self._lock:
            rec = self._operations.get(op_id)
            if not rec:
                return False
            rec.cancel_requested = True
            if rec.status in ("accepted", "running"):
                rec.status = "canceled"
            return True

    def get(self, op_id: str) -> Optional[OperationRecord]:
        with self._lock:
            return self._operations.get(op_id)


mono_queue = MonoQueue()
operation_manager = OperationManager()
