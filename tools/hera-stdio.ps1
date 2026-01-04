$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

# Resolve Blender executable
$blenderExe = $env:BLENDER_EXE
if (-not $blenderExe -or -not (Test-Path $blenderExe)) {
    $candidates = @(
        "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        "D:\Blender_5.0.0_Portable\blender.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $blenderExe = $c; break }
    }
}

if (-not $blenderExe -or -not (Test-Path $blenderExe)) {
    [Console]::Error.WriteLine("HERA stdio: Blender executable not found. Set BLENDER_EXE or install Blender 5.0.")
    exit 1
}

$pythonScript = Join-Path $repoRoot "tools\run_stdio_blender.py"
$cmdLine = "`"$blenderExe`" -b --factory-startup --python `"$pythonScript`""

[Console]::Error.WriteLine("HERA stdio: launching Blender via cmd.exe for Claude Desktop compatibility...")
cmd.exe /c $cmdLine
$code = $LASTEXITCODE
[Console]::Error.WriteLine("HERA stdio: Blender exited (code=$code)")
exit $code
