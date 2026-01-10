# src/hera_mcp/server/socket_server.py
"""
MCP Socket (WebSocket) Server
- Proxy PUR vers le handler stdio existant
- AUCUNE connaissance des tools
- AUCUNE duplication de logique
- Contrat MCP figé
"""

from __future__ import annotations

import asyncio
import json
import traceback
from typing import Any, Dict

import websockets

# IMPORT CANONIQUE : core comme source de verite
from hera_mcp.server import core

# -------------------------
# Helpers JSON strict
# -------------------------

def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _json_loads(txt: str) -> Any:
    return json.loads(txt)

def _error(code: str, message: str, details: Dict[str, Any] | None = None):
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }

# -------------------------
# MCP Message Handling
# -------------------------

async def handle_message(message: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return core.handle(message)
    except Exception as exc:
        traceback.print_exc()
        return _error(
            "internal_error",
            "Unhandled exception in socket transport",
            {"exception": str(exc)},
        )
# -------------------------
# WebSocket Server
# -------------------------

async def _client_loop(ws):
    try:
        async for raw in ws:
            try:
                data = _json_loads(raw)
            except Exception:
                await ws.send(
                    _json_dumps(
                        _error("invalid_json", "Payload is not valid JSON")
                    )
                )
                continue

            # stdio peut être sync → on protège
            result = handle_message(data)
            if asyncio.iscoroutine(result):
                result = await result

            await ws.send(_json_dumps(result))
    except (ConnectionResetError, OSError):
        # Client dropped the TCP connection (common on Windows).
        return
    except Exception as exc:
        # If websockets closes without close frame, swallow quietly.
        try:
            from websockets.exceptions import ConnectionClosed
            if isinstance(exc, ConnectionClosed):
                return
        except Exception:
            pass
        raise



async def serve_socket(host: str = "127.0.0.1", port: int = 8765):
    """
    Start MCP WebSocket server.
    Blocking call (run inside Blender or thread).
    """
    async with websockets.serve(_client_loop, host, port):
        print(f"[HERA MCP SOCKET] listening on ws://{host}:{port}")
        await asyncio.Future()  # run forever

# -------------------------
# CLI / Debug
# -------------------------

def main():
    asyncio.run(serve_socket())

if __name__ == "__main__":
    main()
