param(
  [string]$Url = "ws://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"
$env:MCP_SOCKET_URL = $Url

function Invoke-Once([string]$jsonLine) {
  $out = $jsonLine | node .\tools\mcp_ws_stdio_server.js --once
  if (-not $out) { throw "No output from ws proxy." }

  $out | Write-Output

  $obj = $out | ConvertFrom-Json
  if ($null -eq $obj.ok) { throw "Response missing .ok" }
  if (-not $obj.ok) {
    $msg = $obj.error.message
    $code = $obj.error.code
    throw "WS proxy call failed: $code - $msg"
  }
  return $obj
}

Write-Host "[smoke] tools/list"
Invoke-Once '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | Out-Null

Write-Host "[smoke] exists"
Invoke-Once '{"type":"tools/call","name":"hera.blender.object.exists","arguments":{"name":"Cube"}}' | Out-Null

Write-Host "[smoke] move"
Invoke-Once '{"type":"tools/call","name":"hera.blender.object.move","arguments":{"name":"Cube","location":[2,2,0]}}' | Out-Null

Write-Host "[smoke] get_location"
Invoke-Once '{"type":"tools/call","name":"hera.blender.object.get_location","arguments":{"name":"Cube"}}' | Out-Null

Write-Host "[smoke] batch"
$batch = @{
  type="tools/call"
  name="hera.blender.batch"
  arguments=@{
    steps=@(
      @{ tool="hera.blender.object.move"; args=@{ name="Cube"; location=@(0,0,0) } }
      @{ tool="hera.blender.object.move"; args=@{ name="Cube"; location=@(1,1,0) } }
      @{ tool="hera.blender.object.get_location"; args=@{ name="Cube" } }
    )
    continue_on_error=$false
  }
} | ConvertTo-Json -Depth 10 -Compress

Invoke-Once $batch | Out-Null

Write-Host "[smoke] OK"
