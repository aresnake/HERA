"""
Action runner.
"""

from __future__ import annotations

from typing import Any, Dict

from .models import ActionContext
from .registry import get as get_action


def run_action(action_name: str, params: Dict[str, Any], ctx: ActionContext) -> Dict[str, Any]:
    """
    Execute an action and return a dict compatible with safe_execute() expectations.
    """
    impl = get_action(action_name)
    if impl is None:
        return {
            "status": "error",
            "error": {
                "code": "not_implemented",
                "message": f"Unknown action: {action_name}",
                "recoverable": False,
            },
        }

    out = impl.execute(params or {}, ctx)
    return out.as_dict()
