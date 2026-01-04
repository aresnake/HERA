from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure repo "src/" is importable inside Blender's Python
REPO_ROOT = Path(__file__).resolve().parents[2]  # D:\HERA
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hera_mcp.tools.core.health import tool_health
from hera_mcp.tools.scene.create_object import tool_create_object
from hera_mcp.tools.scene.move_object import tool_move_object
from hera_mcp.tools.scene.snapshot import tool_scene_snapshot


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    # 1) health
    r1 = tool_health()
    _assert(r1.get("status") == "success", f"health status != success: {r1}")
    _assert("scene_state" in r1, "health missing scene_state")

    # 2) create cube (data-first)
    r2 = tool_create_object(type="CUBE", name="HERA_Cube", location=[1, 2, 3])
    _assert(r2.get("status") == "success", f"create status != success: {r2}")
    created = r2.get("data", {}).get("diff", {}).get("created", [])
    _assert("HERA_Cube" in created, f"created diff missing HERA_Cube: {r2}")

    # 3) move object
    r3 = tool_move_object(name="HERA_Cube", location=[4, 5, 6])
    _assert(r3.get("status") == "success", f"move status != success: {r3}")
    modified = r3.get("data", {}).get("diff", {}).get("modified", [])
    _assert("HERA_Cube" in modified, f"modified diff missing HERA_Cube: {r3}")

    # 4) snapshot
    r4 = tool_scene_snapshot(limit_objects=50)
    _assert(r4.get("status") == "success", f"snapshot status != success: {r4}")
    ss = r4.get("scene_state", {})
    _assert(ss.get("ok") is True, f"scene_state ok != True: {ss}")

    print("TEST_RESULT:" + json.dumps({"ok": True, "steps": ["health", "create", "move", "snapshot"]}))


if __name__ == "__main__":
    main()
