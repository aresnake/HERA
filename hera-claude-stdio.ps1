param(
  [string]$Url = "ws://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$env:MCP_SOCKET_URL = $Url

# Important: Claude parle en stdio → on forward 1 ligne = 1 requête
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($null -eq $line) { break }

  $out = $line | node "$PSScriptRoot\mcp_ws_stdio_server.js" --once
  if ($out) {
    [Console]::Out.WriteLine($out)
  }
}
