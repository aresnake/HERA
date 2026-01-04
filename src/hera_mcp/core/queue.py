"""
Single-thread execution gate for Blender-safe operations.
"""

from __future__ import annotations

import threading
from typing import Callable, TypeVar

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


mono_queue = MonoQueue()
