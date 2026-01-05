"""
Core action models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ActionContext:
    """
    Runtime context passed to actions.
    - scene_state_provider: callable returning a compact scene snapshot dict
    - extras: future-proof bag (config, policies, etc.)
    """
    scene_state_provider: Any
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionOutput:
    """
    Standard result returned by actions (tool-like payload).
    This is intentionally close to current tool return format so safe_execute stays unchanged.
    """
    status: str = "success"
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    # optional tool fields
    scene_state: Optional[Dict[str, Any]] = None
    resume_token: Optional[Dict[str, Any]] = None
    next_actions: Optional[Any] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    data_diff: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"status": self.status}
        if self.data is not None:
            out["data"] = self.data
        if self.error is not None:
            out["error"] = self.error
        if self.scene_state is not None:
            out["scene_state"] = self.scene_state
        if self.resume_token is not None:
            out["resume_token"] = self.resume_token
        if self.next_actions is not None:
            out["next_actions"] = self.next_actions
        if self.metrics:
            out["metrics"] = self.metrics
        if self.data_diff is not None:
            out["data_diff"] = self.data_diff
        return out
