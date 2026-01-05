$ErrorActionPreference = "Stop"

function ErrLine([string]$msg) {
  [Console]::Error.WriteLine($msg)
}

try {
  $launcherPath = "D:\HERA\tools\hera-stdio.ps1"
  $cmdExe = "C:\Windows\System32\cmd.exe"
  $pwshExe = "C:\Program Files\PowerShell\7\pwsh.exe"

  # Resolve config path
  $appData = $env:APPDATA
  $localAppData = $env:LOCALAPPDATA
  $path1 = Join-Path -Path $appData -ChildPath "Claude\claude_desktop_config.json"
  $path2 = Join-Path -Path $localAppData -ChildPath "AnthropicClaude\claude_desktop_config.json"

  $configPath = $null
  foreach ($p in @($path1, $path2)) {
    if ($p -and (Test-Path -LiteralPath $p)) { $configPath = $p; break }
  }
  if (-not $configPath) {
    $configPath = $path1
    $dir = Split-Path -Parent $configPath
    if (-not (Test-Path -LiteralPath $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
  }

  # Load existing config safely
  $cfg = @{}
  if (Test-Path -LiteralPath $configPath) {
    $raw = Get-Content -Path $configPath -Raw -Encoding UTF8
    if ($raw.Trim().Length -gt 0) {
      try {
        $parsed = $raw | ConvertFrom-Json -ErrorAction Stop
        if ($parsed) { $cfg = $parsed }
      } catch { }
    }
  }
  if (-not $cfg) { $cfg = @{} }

  # Ensure mcpServers is a Hashtable
  if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers")) {
    $cfg.mcpServers = @{}
  } else {
    if ($cfg.mcpServers -is [System.Management.Automation.PSCustomObject]) {
      $tmp = @{}
      foreach ($k in $cfg.mcpServers.PSObject.Properties.Name) { $tmp[$k] = $cfg.mcpServers.$k }
      $cfg.mcpServers = $tmp
    } elseif (-not ($cfg.mcpServers -is [System.Collections.IDictionary])) {
      $cfg.mcpServers = @{}
    }
  }

  $argString = "`"$pwshExe`" -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$launcherPath`""
  $cfg.mcpServers["hera-blender"] = @{
    command = $cmdExe
    args    = @("/c", $argString)
    env     = @{}
  }

  $json = $cfg | ConvertTo-Json -Depth 20 -Compress:$false
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($configPath, $json, $utf8NoBom)

  ErrLine "Updated Claude Desktop MCP config at $configPath (server: hera-blender)"
  ErrLine "command=$cmdExe"
  ErrLine ("args=" + ($cfg.mcpServers["hera-blender"].args -join " "))
  exit 0
}
catch {
  ErrLine $_.ToString()
  exit 1
}
