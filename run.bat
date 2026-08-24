@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
if /i "%~1"=="--venv" set "VENV=%~2"

if not exist "%VENV%\Scripts\pythonw.exe" (
    echo no environment at "%VENV%"
    echo run setup.bat first
    exit /b 1
)

start "" "%VENV%\Scripts\pythonw.exe" -m avatar_core
exit /b 0
