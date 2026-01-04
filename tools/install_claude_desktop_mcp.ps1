$ErrorActionPreference = "Stop"

try {
    # Resolve launcher and PowerShell path
    $launcherPath = "D:\HERA\tools\hera-stdio.ps1"
    $pwshPath = $null
    try {
        $cmd = Get-Command pwsh -ErrorAction Stop
        $pwshPath = $cmd.Source
    } catch { }
    if (-not $pwshPath) {
        $pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
    }

    # Resolve config path
    $appData = $env:APPDATA
    $localAppData = $env:LOCALAPPDATA
    $path1 = Join-Path -Path $appData -ChildPath "Claude\claude_desktop_config.json"
    $path2 = Join-Path -Path $localAppData -ChildPath "AnthropicClaude\claude_desktop_config.json"

    $configPath = $null
    foreach ($p in @($path1, $path2)) {
        if ($p -and (Test-Path $p)) { $configPath = $p; break }
    }
    if (-not $configPath) {
        $configPath = $path1
        $configDir = Split-Path -Parent $configPath
        if (-not (Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
    }

    # Load existing config (tolerate empty/invalid)
    $cfg = @{}
    if (Test-Path $configPath) {
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

    # Build env map
    $envMap = @{}
    if ($env:BLENDER_EXE -and (Test-Path $env:BLENDER_EXE)) {
        $envMap.BLENDER_EXE = $env:BLENDER_EXE
    }

    $cfg.mcpServers["hera-blender"] = @{
        command = $pwshPath
        args    = @("-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",$launcherPath)
        env     = $envMap
    }

    $json = $cfg | ConvertTo-Json -Depth 20 -Compress:$false
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $json, $utf8NoBom)

    [Console]::Error.WriteLine("Updated Claude Desktop MCP config at $configPath (server: hera-blender) launcher=$launcherPath")
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.ToString())
    exit 1
}
