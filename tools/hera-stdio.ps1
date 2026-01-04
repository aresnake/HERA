$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not $env:BLENDER_EXE -or -not (Test-Path $env:BLENDER_EXE)) {
    $candidates = @(
        "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        "D:\Blender_5.0.0_Portable\blender.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $env:BLENDER_EXE = $c; break }
    }
}

if (-not $env:BLENDER_EXE -or -not (Test-Path $env:BLENDER_EXE)) {
    [Console]::Error.WriteLine("HERA stdio: Blender executable not found. Set BLENDER_EXE or install Blender 5.0.")
    exit 1
}

[Console]::Error.WriteLine("HERA stdio: launching Blender with inherited stdio...")
$pythonScript = Join-Path $repoRoot "tools\run_stdio_blender.py"

& "$env:BLENDER_EXE" -b --factory-startup --python "$pythonScript"
$code = $LASTEXITCODE
[Console]::Error.WriteLine("HERA stdio: Blender exited (code=$code)")
exit $code
