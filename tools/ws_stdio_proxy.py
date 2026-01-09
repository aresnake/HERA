# tools/ws_stdio_proxy.py
"""
Proxy MCP: stdin/stdout <-> WebSocket

Claude Desktop parle MCP via stdio (stdin/stdout).
Blender UI expose MCP via WebSocket (ws://127.0.0.1:8765).

Ce proxy:
- lit chaque ligne JSON depuis stdin
- l'envoie au serveur WebSocket
- attend la réponse
- l'écrit sur stdout (1 ligne JSON)
IMPORTANT: aucun print sur stdout à part les réponses.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import websockets


async def main(url: str) -> int:
    # logs uniquement sur stderr
    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    return 0  # stdin fermé

                # Claude envoie du JSON par ligne. On trim juste le \n.
                payload = line.rstrip("\r\n")
                if not payload:
                    continue

                await ws.send(payload)
                resp = await ws.recv()

                # réponse = 1 ligne JSON
                sys.stdout.write(resp + "\n")
                sys.stdout.flush()
    except Exception as exc:
        sys.stderr.write(f"[ws-stdio-proxy] ERROR: {exc}\n")
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8765")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.url)))
