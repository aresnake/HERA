# tools/ui_bridge.py
# Lance le serveur MCP HERA DANS Blender UI (mode interactif)

import sys
import threading
import traceback
from pathlib import Path
import inspect

print("=== HERA UI BRIDGE STARTING ===")

# Ajouter D:\HERA\src au PYTHONPATH de Blender
HERA_ROOT = Path(__file__).resolve().parents[1]
HERA_SRC = HERA_ROOT / "src"

if str(HERA_SRC) not in sys.path:
    sys.path.insert(0, str(HERA_SRC))
    print(f"[HERA] Added to sys.path: {HERA_SRC}")

def start_mcp():
    try:
        import hera_mcp.server.stdio as stdio

        print("HERA MCP module loaded:", stdio.__file__)

        # Détection du point d’entrée
        if hasattr(stdio, "serve_stdio"):
            entry = stdio.serve_stdio
            name = "serve_stdio"
        elif hasattr(stdio, "run"):
            entry = stdio.run
            name = "run"
        elif hasattr(stdio, "main"):
            entry = stdio.main
            name = "main"
        else:
            raise RuntimeError(
                "No MCP entrypoint found in hera_mcp.server.stdio "
                "(expected serve_stdio / run / main)"
            )

        print(f"[HERA] Using stdio.{name}")
        print("HERA MCP server starting (UI mode)...")

        # 🔑 Appel ADAPTATIF (avec ou sans ui_mode)
        sig = inspect.signature(entry)
        if "ui_mode" in sig.parameters:
            entry(ui_mode=True)
        else:
            entry()

    except Exception:
        print("❌ HERA MCP failed to start")
        traceback.print_exc()

# Lancer MCP dans un thread pour ne PAS bloquer Blender UI
thread = threading.Thread(target=start_mcp, daemon=True)
thread.start()

print("=== HERA UI MCP READY ===")
