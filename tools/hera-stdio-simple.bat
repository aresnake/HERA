@echo off
REM Version simple - assume que le worker Blender tourne déjà
REM Lance juste le serveur stdio MCP

set "HERA_ROOT=D:\HERA"
set "PYTHON_EXE=%HERA_ROOT%\.venv\Scripts\python.exe"
set "HERA_BLENDER_PORT=8766"

REM Vérifier que Python existe
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at %PYTHON_EXE% 1>&2
    exit /b 1
)

REM Vérifier que le worker est accessible
echo [hera-stdio-simple] Testing worker at port %HERA_BLENDER_PORT%... 1>&2
curl -s http://127.0.0.1:%HERA_BLENDER_PORT%/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Blender worker not reachable on port %HERA_BLENDER_PORT% 1>&2
    echo [ERROR] Please run start-worker.bat first! 1>&2
    exit /b 1
)

echo [hera-stdio-simple] Worker OK, starting stdio server... 1>&2

REM Lancer le serveur stdio (stdout doit être propre JSON-RPC)
"%PYTHON_EXE%" -m hera_mcp.server.stdio
