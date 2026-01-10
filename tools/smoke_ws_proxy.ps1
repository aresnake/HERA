param(
  [string]$Url = "ws://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$env:MCP_SOCKET_URL = $Url

function CallOnce([string]$jsonLine) {
  $out = $jsonLine | node .\tools\mcp_ws_stdio_server.js --once
  $out | Write-Output
  ($out | ConvertFrom-Json) | Out-Null
}

Write-Host "[smoke] tools/list"
'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node .\tools\mcp_ws_stdio_server.js --once | Out-Null

Write-Host "[smoke] exists"
CallOnce '{"type":"tools/call","name":"hera.blender.object.exists","arguments":{"name":"Cube"}}' | Out-Null

Write-Host "[smoke] move"
CallOnce '{"type":"tools/call","name":"hera.blender.object.move","arguments":{"name":"Cube","location":[2,2,0]}}' | Out-Null

Write-Host "[smoke] get_location"
CallOnce '{"type":"tools/call","name":"hera.blender.object.get_location","arguments":{"name":"Cube"}}' | Out-Null

Write-Host "[smoke] OK"
