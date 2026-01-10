@echo off
REM Wrapper batch pour lancer hera-stdio.ps1 avec le bon environnement
REM Ce script est appelé par Claude Desktop

set "HERA_ROOT=D:\HERA"
set "PYTHON_EXE=%HERA_ROOT%\.venv\Scripts\python.exe"

REM Ajouter le Python du venv au PATH temporairement
set "PATH=%HERA_ROOT%\.venv\Scripts;%PATH%"

REM Chercher Blender (optionnel, le script PS1 cherche aussi)
if exist "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" (
    set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
) else if exist "D:\Blender_5.0.0_Portable\blender.exe" (
    set "BLENDER_EXE=D:\Blender_5.0.0_Portable\blender.exe"
)

REM Lancer le script PowerShell
powershell.exe -ExecutionPolicy Bypass -File "%HERA_ROOT%\tools\hera-stdio.ps1"
