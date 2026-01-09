# tools/launch_blender_ui.ps1
# Lance Blender UI avec HERA MCP injecté (mode rush)

$BLENDER = "D:\Blender_5.0.0_Portable\blender.exe"
$HERA_ROOT = "D:\HERA"
$SCRIPT = "$HERA_ROOT\tools\ui_bridge.py"

if (-not (Test-Path $BLENDER)) {
    Write-Error "❌ Blender not found: $BLENDER"
    exit 1
}

if (-not (Test-Path $SCRIPT)) {
    Write-Error "❌ UI bridge script not found: $SCRIPT"
    exit 1
}

Write-Host "🚀 Launching Blender UI with HERA MCP"
Write-Host "Blender: $BLENDER"
Write-Host "Bridge : $SCRIPT"

& $BLENDER --python $SCRIPT
