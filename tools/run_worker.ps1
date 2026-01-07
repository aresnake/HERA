param(
  [int]$Port = 8766
)

$ErrorActionPreference = "Stop"

# Repo root
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ROOT = Split-Path -Parent $ROOT
Set-Location $ROOT

# Pick Blender
$paths = @(
  $env:BLENDER_EXE,
  "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
  "D:\Blender_5.0.0_Portable\blender.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if (-not $paths) { throw "No Blender found. Set `$env:BLENDER_EXE to blender.exe" }

$blender = $paths[0]
Write-Host "[run_worker] Using Blender: $blender"
Write-Host "[run_worker] Port: $Port"

& $blender -b --python "$ROOT\tools\blender_worker.py" -- --port $Port
