# tools/hera-stdio.ps1
# Claude Desktop stdio launcher (stdout-pure via tools/stdio_proxy.py)

$ErrorActionPreference = "Stop"

function ErrLine([string]$msg) {
  [Console]::Error.WriteLine($msg)
}

try {
  # repo root = parent of tools/
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $repoRoot  = Split-Path -Parent $scriptDir

  # Resolve Blender exe
  $candidates = @()
  if ($env:BLENDER_EXE) { $candidates += $env:BLENDER_EXE }
  $candidates += @(
    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    "D:\Blender_5.0.0_Portable\blender.exe"
  )

  $blenderExe = $null
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) { $blenderExe = $c; break }
  }
  if (-not $blenderExe) {
    ErrLine "HERA stdio: Blender not found. Set `$env:BLENDER_EXE or install Blender 5.0."
    exit 1
  }

  # Resolve Python (prefer py -3, else python)
  $pyCmd = $null
  $pyArgsPrefix = @()
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    $pyCmd = $py.Source
    $pyArgsPrefix = @("-3")
  } else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
      $pyCmd = $python.Source
      $pyArgsPrefix = @()
    }
  }
  if (-not $pyCmd) {
    ErrLine "HERA stdio: Python not found (need py or python in PATH)."
    exit 1
  }

  $proxy = Join-Path $repoRoot "tools\stdio_proxy.py"
  $runner = Join-Path $repoRoot "tools\run_stdio_blender.py"
  if (-not (Test-Path -LiteralPath $proxy)) { ErrLine "HERA stdio: missing $proxy"; exit 1 }
  if (-not (Test-Path -LiteralPath $runner)) { ErrLine "HERA stdio: missing $runner"; exit 1 }

  ErrLine "HERA stdio: launching stdout-clean proxy -> Blender..."
  # IMPORTANT: the `--` is REQUIRED (argparse)
  $args = @()
  $args += $pyArgsPrefix
  $args += @("-u", $proxy, "--", $blenderExe, "-b", "--factory-startup", "--python", $runner)

  & $pyCmd @args
  $code = $LASTEXITCODE
  ErrLine "HERA stdio: exited (code=$code)"
  exit $code
}
catch {
  ErrLine ("HERA stdio: launcher failed: " + $_.Exception.Message)
  exit 1
}
