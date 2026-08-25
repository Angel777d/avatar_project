@echo off
setlocal
set "APP=avatar"
set "NAME=Avatar"
set "DIR=%LOCALAPPDATA%\%APP%"
set "BASE=https://github.com/Angel777d/avatar_project/releases/latest/download"

mkdir "%DIR%" 2>nul
curl -fsSL -o "%DIR%\supervisor.exe" "%BASE%/supervisor.exe" || goto :fail
curl -fsSL -o "%DIR%\config.json"    "%BASE%/config.json"    || goto :fail

rem No seed file: the catalogue every plugin is chosen from ships inside avatar_manager,
rem and config.json already names what a fresh install runs with.

rem Ask the shell for Desktop rather than assuming %USERPROFILE%\Desktop, which is wrong
rem wherever OneDrive has redirected it. Written only when absent, so a user who moved or
rem deleted it does not get it back on every update. Never fatal.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path ([Environment]::GetFolderPath('Desktop')) '%NAME%.lnk'; if (-not (Test-Path $p)) { $s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath = '%DIR%\supervisor.exe'; $s.WorkingDirectory = '%DIR%'; $s.Description = '%NAME%'; $s.Save() }" >nul 2>&1

start "" "%DIR%\supervisor.exe"
exit /b 0

:fail
echo Install failed.
pause
exit /b 1
