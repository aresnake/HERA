@echo off
REM Lance juste le worker Blender en arrière-plan
REM A lancer AVANT de démarrer Claude Desktop

set "HERA_ROOT=D:\HERA"
set "TMP_DIR=%HERA_ROOT%\.tmp"
set "READY_FILE=%TMP_DIR%\worker_ready.json"

REM Créer le dossier tmp
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

REM Nettoyer les anciens fichiers
if exist "%READY_FILE%" del /Q "%READY_FILE%"

REM Trouver Blender
set "BLENDER_EXE="
if exist "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
) else if exist "D:\Blender_5.0.0_Portable\blender.exe" (
    set "BLENDER_EXE=D:\Blender_5.0.0_Portable\blender.exe"
) else (
    echo [ERROR] Blender not found!
    pause
    exit /b 1
)

echo Starting Blender worker...
echo Blender: %BLENDER_EXE%
echo Ready file: %READY_FILE%

REM Lancer Blender worker
start "HERA Blender Worker" /MIN "%BLENDER_EXE%" -b --factory-startup --disable-autoexec --python "%HERA_ROOT%\tools\blender_worker.py" -- --port 8766 --ready-file "%READY_FILE%"

echo.
echo Waiting for worker to be ready...
timeout /t 2 /nobreak >nul

:wait_loop
if exist "%READY_FILE%" goto ready_found
timeout /t 1 /nobreak >nul
goto wait_loop

:ready_found
echo.
echo *** Worker is READY! ***
echo You can now start Claude Desktop.
echo.
echo To stop the worker, close the Blender window or run: taskkill /IM blender.exe
echo.
pause
