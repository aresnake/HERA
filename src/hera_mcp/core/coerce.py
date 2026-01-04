"""
Tolerant coercion helpers for inputs coming from MCP clients.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def to_vector3(value, default=(0.0, 0.0, 0.0)) -> Tuple[float, float, float]:
    if value is None:
        return tuple(default)
    if isinstance(value, (int, float)):
        return (float(value), float(value), float(value))
    if isinstance(value, dict):
        keys = ["x", "y", "z"]
        return tuple(to_float(value.get(k, d)) for k, d in zip(keys, default))
    if isinstance(value, Iterable):
        values: List[float] = [to_float(v, d) for v, d in zip(value, default)]
        while len(values) < 3:
            values.append(0.0)
        return tuple(values[:3])
    return tuple(default)


def to_name(value, fallback: str = "unnamed") -> str:
    try:
        text = str(value).strip()
        return text or fallback
    except Exception:
        return fallback
