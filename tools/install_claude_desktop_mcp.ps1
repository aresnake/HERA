$ErrorActionPreference = "Stop"

try {
    $appData = $env:APPDATA
    $localAppData = $env:LOCALAPPDATA

    $candidates = @(
        Join-Path $appData "Claude\claude_desktop_config.json",
        Join-Path $localAppData "AnthropicClaude\claude_desktop_config.json"
    )

    $configPath = $null
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $configPath = $c
            break
        }
    }

    if (-not $configPath) {
        $configPath = $candidates[0]
        $configDir = Split-Path -Parent $configPath
        if (-not (Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir | Out-Null
        }
    }

    $config = @{}
    if (Test-Path $configPath) {
        $jsonText = Get-Content -Path $configPath -Raw -Encoding UTF8
        if ($jsonText.Trim().Length -gt 0) {
            $config = $jsonText | ConvertFrom-Json -ErrorAction SilentlyContinue
        }
    }
    if (-not $config) { $config = @{} }

    if (-not $config.ContainsKey("mcpServers")) {
        $config["mcpServers"] = @{}
    }

    $config["mcpServers"]["hera-blender"] = @{
        command = "powershell"
        args    = @("-ExecutionPolicy","Bypass","-File","D:\HERA\tools\hera-stdio.ps1")
        env     = @{}
    }

    $configJson = $config | ConvertTo-Json -Depth 10 -Compress:$false
    [System.IO.File]::WriteAllText($configPath, $configJson, [System.Text.Encoding]::UTF8)

    [Console]::Error.WriteLine("Updated Claude Desktop MCP config at $configPath with server 'hera-blender'.")
    exit 0
}
catch {
    [Console]::Error.WriteLine("Failed to update Claude Desktop MCP config: $_")
    exit 1
}
