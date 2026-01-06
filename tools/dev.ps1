param(
  [switch]$Test
)

$ErrorActionPreference = "Stop"

# Always run from repo root
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Split-Path -Parent $ROOT
Set-Location $ROOT

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

. .\.venv\Scripts\Activate.ps1

python -m pip install -U pip
python -m pip install -e .

if ($Test) {
  python -m pytest
} else {
  Write-Host "HERA dev env ready. Run: .\tools\dev.ps1 -Test"
}
