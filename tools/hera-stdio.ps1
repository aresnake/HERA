param(
  [string]$BlenderExe = $env:BLENDER_EXE
)

$ErrorActionPreference = "Stop"

function LogErr([string]$msg) {
  [Console]::Error.WriteLine($msg)
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tmp  = Join-Path $Root ".tmp"
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

$Ready = Join-Path $Tmp "worker_ready.json"
$Out   = Join-Path $Tmp "worker_out.txt"
$Err   = Join-Path $Tmp "worker_err.txt"

Remove-Item -Force -ErrorAction SilentlyContinue $Ready, $Out, $Err

function Pick-Blender {
  param([string]$Candidate)
  $paths = @(
    $Candidate,
    $env:BLENDER_EXE,
    "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    "D:\Blender_5.0.0_Portable\blender.exe"
  ) | Where-Object { $_ -and (Test-Path $_) }

  if (-not $paths) { throw "No Blender found. Set BLENDER_EXE or install Blender." }
  return (Resolve-Path $paths[0]).Path
}

$blender = Pick-Blender $BlenderExe
$worker  = (Resolve-Path (Join-Path $Root "tools\blender_worker.py")).Path

LogErr "[hera-stdio] root=$Root"
LogErr "[hera-stdio] blender=$blender"
LogErr "[hera-stdio] worker=$worker"
LogErr "[hera-stdio] ready=$Ready"

# Start Blender worker headless (background)
$p = Start-Process -PassThru -NoNewWindow `
  -FilePath $blender `
  -ArgumentList @(
    "-b","--factory-startup","--disable-autoexec",
    "--python",$worker,
    "--","--port","0","--ready-file",$Ready
  ) `
  -RedirectStandardOutput $Out `
  -RedirectStandardError  $Err

try {
  # Wait ready-file
  $t0 = Get-Date
  while (-not (Test-Path $Ready)) {
    if ($p.HasExited) {
      $tailOut = if (Test-Path $Out) { Get-Content $Out -Tail 120 -ErrorAction SilentlyContinue } else { @() }
      $tailErr = if (Test-Path $Err) { Get-Content $Err -Tail 120 -ErrorAction SilentlyContinue } else { @() }
      throw ("Worker exited early rc={0}`n--- OUT ---`n{1}`n--- ERR ---`n{2}" -f $p.ExitCode, ($tailOut -join "`n"), ($tailErr -join "`n"))
    }
    if (((Get-Date) - $t0).TotalSeconds -gt 30) {
      $tailOut = if (Test-Path $Out) { Get-Content $Out -Tail 120 -ErrorAction SilentlyContinue } else { @() }
      $tailErr = if (Test-Path $Err) { Get-Content $Err -Tail 120 -ErrorAction SilentlyContinue } else { @() }
      throw ("Timeout waiting ready-file.`n--- OUT ---`n{0}`n--- ERR ---`n{1}" -f ($tailOut -join "`n"), ($tailErr -join "`n"))
    }
    Start-Sleep -Milliseconds 200
  }

  $info = Get-Content $Ready -Raw | ConvertFrom-Json
  $env:HERA_BLENDER_PORT = [string]$info.port
  LogErr "[hera-stdio] HERA_BLENDER_PORT=$env:HERA_BLENDER_PORT"

  # IMPORTANT: stdio server must own stdout (JSON-RPC only)
  $python = if (Test-Path (Join-Path $Root ".venv\Scripts\python.exe")) {
    (Resolve-Path (Join-Path $Root ".venv\Scripts\python.exe")).Path
  } else {
    "python"
  }
  LogErr "[hera-stdio] python=$python"
  & $python -m hera_mcp.server.stdio
}
finally {
  if ($p -and -not $p.HasExited) {
    LogErr "[hera-stdio] stopping worker pid=$($p.Id)"
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
  }
}
