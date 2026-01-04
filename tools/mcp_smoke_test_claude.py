from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def find_shell() -> str | None:
    for candidate in ("pwsh", "powershell"):
        if subprocess.call(
            [candidate, "-NoLogo", "-NoProfile", "-Command", "exit 0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0:
            return candidate
    return None


def main() -> int:
    shell = find_shell()
    if not shell:
        print("No PowerShell found (pwsh or powershell).", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    launcher = repo_root / "tools" / "hera-stdio.ps1"
    if not launcher.exists():
        print(f"Launcher not found: {launcher}", file=sys.stderr)
        return 1

    proc = subprocess.Popen(
        [
            shell,
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(launcher),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "hera.health", "arguments": {}},
        },
        {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 5, "method": "prompts/list"},
    ]

    results = []
    try:
        for msg in messages:
            line = json.dumps(msg)
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
            resp_line = proc.stdout.readline()
            if not resp_line:
                print("No response from server.", file=sys.stderr)
                return 1
            try:
                resp = json.loads(resp_line)
            except Exception as exc:
                print(f"Invalid JSON from server: {resp_line} ({exc})", file=sys.stderr)
                return 1
            results.append(resp)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    ok = True
    for resp in results:
        if "result" not in resp and "error" not in resp:
            ok = False
            print(f"Missing result/error in response: {resp}", file=sys.stderr)

    if ok:
        print("Smoke test successful: received JSON-RPC results for initialize/tools/list/call/resources/prompts.", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
