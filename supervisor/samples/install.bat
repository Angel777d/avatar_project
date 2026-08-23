@echo off
setlocal
set "APP=avatar"
set "DIR=%LOCALAPPDATA%\%APP%"
set "BASE=https://github.com/Angel777d/avatar_project/releases/latest/download"

mkdir "%DIR%" 2>nul
curl -fsSL -o "%DIR%\supervisor.exe" "%BASE%/supervisor.exe" || goto :fail
curl -fsSL -o "%DIR%\config.json"    "%BASE%/config.json"    || goto :fail

if not exist "%DIR%\seed.json" >"%DIR%\seed.json" echo {"registries":["https://raw.githubusercontent.com/Angel777d/avatar_registry/main/registry.json"],"plugins":["avatar_kanban","avatar_calendar","avatar_pomodoro","avatar_stats"]}

start "" "%DIR%\supervisor.exe"
exit /b 0

:fail
echo Install failed.
pause
exit /b 1
