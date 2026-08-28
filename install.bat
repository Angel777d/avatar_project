@echo off
setlocal
set "APP=avatar"
set "NAME=Avatar"
set "DIR=%LOCALAPPDATA%\%APP%"
set "BASE=https://github.com/Angel777d/avatar_project/releases/latest/download"

set "UV_UNMANAGED_INSTALL=%DIR%\uv"
set "UV_PYTHON_INSTALL_DIR=%DIR%\python"
set "UV_PYTHON_INSTALL_BIN=0"
set "UV_CACHE_DIR=%DIR%\cache"

mkdir "%DIR%" 2>nul
curl -fsSL -o "%DIR%\config.json"   "%BASE%/config.json"   || goto :fail
curl -fsSL -o "%DIR%\supervisor.py" "%BASE%/supervisor.py" || goto :fail
curl -fsSL -o "%DIR%\avatar.ico"    "%BASE%/avatar.ico"    >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" >nul 2>&1
if not exist "%DIR%\uv\uv.exe" echo Could not install uv. & goto :fail

"%DIR%\uv\uv.exe" python install 3.13 || goto :fail

set "PYW="
for /f "delims=" %%p in ('"%DIR%\uv\uv.exe" python find 3.13 2^>nul') do set "PY=%%p"
if defined PY set "PYW=%PY:python.exe=pythonw.exe%"
if not defined PYW echo Could not find the interpreter. & goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path ([Environment]::GetFolderPath('Desktop')) '%NAME%.lnk'; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath = '%PYW%'; $s.Arguments = '\"%DIR%\supervisor.py\"'; $s.WorkingDirectory = '%DIR%'; $s.Description = '%NAME%'; if (Test-Path '%DIR%\avatar.ico') { $s.IconLocation = '%DIR%\avatar.ico,0' }; $s.Save()" >nul 2>&1

"%PYW%" "%DIR%\supervisor.py" --check
if errorlevel 3 (
    echo Avatar is already running. The update applies the next time it starts.
    exit /b 0
)
if errorlevel 1 (
    echo Avatar cannot start. See "%DIR%\supervisor.log".
    pause
    exit /b 1
)

start "" "%PYW%" "%DIR%\supervisor.py"
exit /b 0

:fail
echo Install failed.
pause
exit /b 1
