@echo off
setlocal
set "APP=avatar"
set "NAME=Avatar"
set "DIR=%LOCALAPPDATA%\%APP%"
set "BASE=https://github.com/Angel777d/avatar_project/releases/latest/download"

mkdir "%DIR%" 2>nul
curl -fsSL -o "%DIR%\supervisor.exe" "%BASE%/supervisor.exe" || goto :fail
curl -fsSL -o "%DIR%\config.json"    "%BASE%/config.json"    || goto :fail

if not exist "%DIR%\seed.json" >"%DIR%\seed.json" echo {"registries":["https://raw.githubusercontent.com/Angel777d/avatar_registry/main/registry.json"],"plugins":["avatar_kanban","avatar_calendar","avatar_pomodoro","avatar_stats"]}

rem Ask the shell for Desktop rather than assuming %USERPROFILE%\Desktop, which is wrong
rem wherever OneDrive has redirected it. Written only when absent, like seed.json, so a
rem user who moved or deleted it does not get it back on every update. Never fatal.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path ([Environment]::GetFolderPath('Desktop')) '%NAME%.lnk'; if (-not (Test-Path $p)) { $s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath = '%DIR%\supervisor.exe'; $s.WorkingDirectory = '%DIR%'; $s.Description = '%NAME%'; $s.Save() }" >nul 2>&1

start "" "%DIR%\supervisor.exe"
exit /b 0

:fail
echo Install failed.
pause
exit /b 1
