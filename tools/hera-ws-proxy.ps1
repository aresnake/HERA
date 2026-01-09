# tools/hera-ws-proxy.ps1
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

# Active le venv HERA si présent (Claude Desktop n'hérite pas forcément de ton shell)
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
  & ".\.venv\Scripts\Activate.ps1"
}

# IMPORTANT: pas de Write-Host (stdout). Si besoin -> stderr.
$env:PYTHONUTF8 = "1"

python ".\tools\ws_stdio_proxy.py" --url "ws://127.0.0.1:8765"
exit $LASTEXITCODE
