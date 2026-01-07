import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stdio_roundtrip():
    script = ROOT / "tools" / "mcp_smoke_test_stdio.py"
    assert script.exists(), f"missing smoke test script: {script}"
    subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=True, timeout=180)
