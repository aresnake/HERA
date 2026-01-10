# tools/blender_ui_socket_bridge.py
"""
Blender UI → HERA MCP Socket Bridge
- À lancer dans Blender UI
- Démarre le serveur socket MCP
"""

import sys
import os
import threading

# 🔧 AJOUT DU SRC AU PATH
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")

if SRC not in sys.path:
    sys.path.insert(0, SRC)
    print("[HERA] Added to sys.path:", SRC)

def _start_socket():
    from hera_mcp.server.socket_server import serve_socket
    import asyncio
    asyncio.run(serve_socket())

def start():
    print("[HERA] Starting MCP socket server inside Blender UI...")
    from hera_mcp.tools import blender_ui_impl
    blender_ui_impl.init_main_thread()
    t = threading.Thread(target=_start_socket, daemon=True)
    t.start()

# Auto-start
start()
