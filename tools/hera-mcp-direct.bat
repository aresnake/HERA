@echo off
REM Version directe sans PowerShell - Lance worker Blender puis serveur stdio
REM Ce script est une alternative si PowerShell pose problème

setlocal enabledelayedexpansion

set "HERA_ROOT=D:\HERA"
set "PYTHON_EXE=%HERA_ROOT%\.venv\Scripts\python.exe"
set "TMP_DIR=%HERA_ROOT%\.tmp"
set "READY_FILE=%TMP_DIR%\worker_ready.json"
set "OUT_FILE=%TMP_DIR%\worker_out.txt"
set "ERR_FILE=%TMP_DIR%\worker_err.txt"

REM Créer le dossier tmp
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

REM Nettoyer les anciens fichiers
if exist "%READY_FILE%" del /Q "%READY_FILE%"
if exist "%OUT_FILE%" del /Q "%OUT_FILE%"
if exist "%ERR_FILE%" del /Q "%ERR_FILE%"

REM Trouver Blender
set "BLENDER_EXE="
if exist "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
) else if exist "D:\Blender_5.0.0_Portable\blender.exe" (
    set "BLENDER_EXE=D:\Blender_5.0.0_Portable\blender.exe"
) else (
    echo [ERROR] Blender not found! 1>&2
    exit /b 1
)

echo [hera-mcp] Blender=%BLENDER_EXE% 1>&2
echo [hera-mcp] Python=%PYTHON_EXE% 1>&2
echo [hera-mcp] Ready=%READY_FILE% 1>&2

REM Lancer Blender worker en arrière-plan
start /B "" "%BLENDER_EXE%" -b --factory-startup --disable-autoexec --python "%HERA_ROOT%\tools\blender_worker.py" -- --port 0 --ready-file "%READY_FILE%" > "%OUT_FILE%" 2> "%ERR_FILE%"

REM Attendre le ready-file (timeout 30 secondes)
set /a timeout=30
set /a elapsed=0

:wait_loop
if exist "%READY_FILE%" goto ready_found
timeout /t 1 /nobreak >nul
set /a elapsed+=1
if %elapsed% geq %timeout% (
    echo [ERROR] Timeout waiting for worker ready-file 1>&2
    type "%OUT_FILE%" 1>&2
    type "%ERR_FILE%" 1>&2
    exit /b 1
)
goto wait_loop

:ready_found
echo [hera-mcp] Worker ready! 1>&2

REM Lire le port depuis le ready-file (parse JSON simple)
for /f "tokens=*" %%a in ('findstr /C:"\"port\"" "%READY_FILE%"') do set PORT_LINE=%%a
for /f "tokens=2 delims=:," %%a in ("!PORT_LINE!") do set HERA_BLENDER_PORT=%%a
set HERA_BLENDER_PORT=%HERA_BLENDER_PORT: =%

echo [hera-mcp] HERA_BLENDER_PORT=%HERA_BLENDER_PORT% 1>&2

REM Lancer le serveur stdio (stdout doit être propre JSON-RPC)
"%PYTHON_EXE%" -m hera_mcp.server.stdio

REM Cleanup: tuer le worker Blender
taskkill /F /IM blender.exe >nul 2>&1

endlocal
