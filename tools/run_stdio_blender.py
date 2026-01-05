"""
Launch the HERA MCP stdio server inside Blender.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    # Emit deterministic readiness token to stderr only.
    sys.stderr.write("HERA_READY\n")
    sys.stderr.flush()
    runpy.run_module("hera_mcp.blender_bridge.mcp_stdio", run_name="__main__")


if __name__ == "__main__":
    main()
