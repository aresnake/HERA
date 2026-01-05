$ErrorActionPreference = "Stop"

function ErrLine([string]$msg) {
  [Console]::Error.WriteLine($msg)
}

try {
  $appData = $env:APPDATA
  $localAppData = $env:LOCALAPPDATA
  $path1 = Join-Path -Path $appData -ChildPath "Claude\claude_desktop_config.json"
  $path2 = Join-Path -Path $localAppData -ChildPath "AnthropicClaude\claude_desktop_config.json"

  $configPath = $null
  foreach ($p in @($path1, $path2)) {
    if ($p -and (Test-Path -LiteralPath $p)) { $configPath = $p; break }
  }
  if (-not $configPath) {
    ErrLine "Config not found in known locations."
    exit 1
  }

  $raw = Get-Content -Path $configPath -Raw -Encoding UTF8
  $cfg = @{}
  if ($raw.Trim().Length -gt 0) {
    try { $parsed = $raw | ConvertFrom-Json -ErrorAction Stop; if ($parsed) { $cfg = $parsed } } catch { }
  }
  if (-not $cfg) { $cfg = @{} }
  if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers")) {
    ErrLine "No mcpServers entry in config."
    exit 1
  }
  $srv = $cfg.mcpServers."hera-blender"
  if (-not $srv) {
    ErrLine "hera-blender entry not found."
    exit 1
  }

  ErrLine ("hera-blender entry: " + ($srv | ConvertTo-Json -Depth 5))

  $command = $srv.command
  $args = $srv.args
  if (-not $command -or -not $args) {
    ErrLine "Missing command or args in hera-blender entry."
    exit 1
  }

  $tmpErr = Join-Path ([System.IO.Path]::GetTempPath()) ("hera_probe_stderr_" + [System.Guid]::NewGuid().ToString("N") + ".log")
  ErrLine "Starting probe: $command $args"
  ErrLine "stderr -> $tmpErr"

  $p = Start-Process -FilePath $command -ArgumentList $args -NoNewWindow -RedirectStandardError $tmpErr -PassThru
  Start-Sleep -Seconds 3
  if (-not $p.HasExited) {
    ErrLine "Probe still running after 3s; stopping..."
    try { $p.Kill() } catch { }
  } else {
    ErrLine "Probe exited early with code $($p.ExitCode)"
  }

  ErrLine "stderr preview:"
  if (Test-Path -LiteralPath $tmpErr) {
    Get-Content -Path $tmpErr -Tail 50 | ForEach-Object { ErrLine $_ }
  } else {
    ErrLine "stderr file not found."
  }

  exit 0
}
catch {
  ErrLine $_.ToString()
  exit 1
}
