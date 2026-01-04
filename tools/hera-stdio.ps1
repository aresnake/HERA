$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

function Get-BlenderExe {
    if ($env:BLENDER_EXE -and (Test-Path $env:BLENDER_EXE)) {
        return $env:BLENDER_EXE
    }
    $candidates = @(
        "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        "D:\Blender_5.0.0_Portable\blender.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

$blenderExe = Get-BlenderExe
if (-not $blenderExe) {
    [Console]::Error.WriteLine("Blender executable not found. Set BLENDER_EXE or install Blender 5.0.")
    exit 1
}

$pythonScript = Join-Path $repoRoot "tools\run_stdio_blender.py"
& $blenderExe -b --factory-startup --python $pythonScript
exit $LASTEXITCODE
