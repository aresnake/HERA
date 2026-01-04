$ErrorActionPreference = "Stop"

try {
    $appData = $env:APPDATA
    $localAppData = $env:LOCALAPPDATA

    $path1 = Join-Path -Path $appData -ChildPath "Claude\claude_desktop_config.json"
    $path2 = Join-Path -Path $localAppData -ChildPath "AnthropicClaude\claude_desktop_config.json"
    $candidates = @($path1, $path2)

    $configPath = $null
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            $configPath = $c
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

    $config = @{}
    if (Test-Path $configPath) {
        $jsonText = Get-Content -Path $configPath -Raw -Encoding UTF8
        if ($jsonText.Trim().Length -gt 0) {
            try {
                $parsed = $jsonText | ConvertFrom-Json -ErrorAction Stop
                if ($parsed) { $config = $parsed }
            }
            catch {
                # ignore invalid JSON, keep empty config
            }
        }
    }

    if (-not $config) { $config = @{} }
    if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
        $config.mcpServers = @{}
    } elseif (-not ($config.mcpServers -is [System.Collections.IDictionary])) {
        $config.mcpServers = @{}
    }

    $config.mcpServers["hera-blender"] = @{
        command = "powershell"
        args    = @("-ExecutionPolicy","Bypass","-File","D:\HERA\tools\hera-stdio.ps1")
        env     = @{}
    }

    $configJson = $config | ConvertTo-Json -Depth 10 -Compress:$false
    [System.IO.File]::WriteAllText($configPath, $configJson, New-Object System.Text.UTF8Encoding($false))

    [Console]::Error.WriteLine("Updated Claude Desktop MCP config at $configPath with server 'hera-blender'.")
    exit 0
}
catch {
    [Console]::Error.WriteLine("Failed to update Claude Desktop MCP config: $_")
    exit 1
}
