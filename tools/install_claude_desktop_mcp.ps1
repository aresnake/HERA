$ErrorActionPreference = "Stop"

try {
    $appData = $env:APPDATA
    $localAppData = $env:LOCALAPPDATA

    $path1 = Join-Path -Path $appData -ChildPath "Claude\claude_desktop_config.json"
    $path2 = Join-Path -Path $localAppData -ChildPath "AnthropicClaude\claude_desktop_config.json"

    $configPath = $null
    foreach ($p in @($path1, $path2)) {
        if ($p -and (Test-Path $p)) {
            $configPath = $p
            break
        }
    }

    if (-not $configPath) {
        $configPath = $path1
        $configDir = Split-Path -Parent $configPath
        if (-not (Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
    }

    $cfg = @{}
    if (Test-Path $configPath) {
        $raw = Get-Content -Path $configPath -Raw -Encoding UTF8
        if ($raw.Trim().Length -gt 0) {
            try {
                $parsed = $raw | ConvertFrom-Json -ErrorAction Stop
                if ($parsed) { $cfg = $parsed }
            } catch {
                # ignore parse errors, keep empty object
            }
        }
    }

    if (-not $cfg) { $cfg = @{} }
    if (-not ($cfg.PSObject.Properties.Name -contains "mcpServers") -or -not ($cfg.mcpServers -is [System.Collections.IDictionary])) {
        $cfg.mcpServers = @{}
    }

    $cfg.mcpServers["hera-blender"] = @{
        command = "powershell"
        args    = @("-ExecutionPolicy","Bypass","-File","D:\HERA\tools\hera-stdio.ps1")
        env     = @{}
    }

    $json = $cfg | ConvertTo-Json -Depth 20 -Compress:$false
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $json, $utf8NoBom)

    [Console]::Error.WriteLine("Updated Claude Desktop MCP config at $configPath (server: hera-blender)")
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.ToString())
    exit 1
}
