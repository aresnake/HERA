"""
Action base interface.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol

from .models import ActionContext, ActionOutput


class Action(Protocol):
    """
    Minimal action protocol: execute(params, ctx) -> ActionOutput
    """
    name: str

    def execute(self, params: Dict[str, Any], ctx: ActionContext) -> ActionOutput:
        ...
