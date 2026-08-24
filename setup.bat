@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "RUNTIME=%ROOT%.python"
set "BRANCH=master"
set "APP_REPO=https://github.com/Angel777d/avatar_project.git"
set "CORE_REPO=https://github.com/Angel777d/angelovich.core.git"
set "FORCE="
set "RUN="

set "PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20260805/cpython-3.13.14+20260805-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
set "PY_SHA=e0df6dea5aa2a7f6fab10ee187abcf1da554e1ebd0aafe4e404ff4a647f92081"

:args
if "%~1"=="" goto args_done
if /i "%~1"=="--force" set "FORCE=1" & shift & goto args
if /i "%~1"=="--run" set "RUN=1" & shift & goto args
if /i "%~1"=="--venv" set "VENV=%~2" & shift & shift & goto args
if /i "%~1"=="--branch" set "BRANCH=%~2" & shift & shift & goto args
if /i "%~1"=="--help" goto usage
echo unknown option: %~1
goto usage
:args_done

echo(
echo avatar_project setup
echo   venv    %VENV%
echo   branch  %BRANCH%
echo(

if defined FORCE if exist "%VENV%" (
    echo removing the old environment
    rmdir /s /q "%VENV%" || goto fail
)

if exist "%VENV%\Scripts\python.exe" (
    echo environment already exists, reusing it ^(--force to rebuild^)
) else (
    call :find_python || call :fetch_python || goto fail
    echo creating the environment with "!PYEXE!"
    "!PYEXE!" -m venv "%VENV%" || goto fail
)

set "VPY=%VENV%\Scripts\python.exe"

echo updating pip
"%VPY%" -m pip install --quiet --upgrade pip || goto fail

where git >nul 2>&1 || (echo git is required to install from github & goto fail)

echo installing the app and its plugins from github
"%VPY%" -m pip install ^
    "angelovich.core @ git+%CORE_REPO%" ^
    "avatar.api @ git+%APP_REPO%@%BRANCH%#subdirectory=api" ^
    "avatar.ui @ git+%APP_REPO%@%BRANCH%#subdirectory=ui" ^
    "avatar.core @ git+%APP_REPO%@%BRANCH%#subdirectory=core" ^
    "avatar_default @ git+%APP_REPO%@%BRANCH%#subdirectory=plugins/avatar" ^
    "avatar_kanban @ git+%APP_REPO%@%BRANCH%#subdirectory=plugins/kanban" ^
    "avatar_calendar @ git+%APP_REPO%@%BRANCH%#subdirectory=plugins/calendar" ^
    "avatar_pomodoro @ git+%APP_REPO%@%BRANCH%#subdirectory=plugins/pomodoro" ^
    "avatar_stats @ git+%APP_REPO%@%BRANCH%#subdirectory=plugins/stats" || goto fail

echo(
echo done. installed:
"%VPY%" -m pip list --format=freeze 2>nul | findstr /i /r "^avatar ^angelovich ^PySide6="
echo(
echo python: %VPY%

if defined RUN (
    echo(
    echo starting the avatar
    start "" "%VENV%\Scripts\pythonw.exe" -m avatar_core
) else (
    echo(
    echo start it with:  run.bat
)
exit /b 0


:find_python
for %%V in (3.14 3.13) do (
    if not defined PYEXE (
        for /f "delims=" %%P in ('py -%%V -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
    )
)
if not defined PYEXE (
    for /f "delims=" %%P in ('python -c "import sys;print(sys.executable if sys.version_info>=(3,13) else '''''')" 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE exit /b 1
echo found python: !PYEXE!
exit /b 0


:fetch_python
echo no python 3.13+ found, downloading a standalone one
if exist "%RUNTIME%\python\python.exe" (
    set "PYEXE=%RUNTIME%\python\python.exe"
    echo reusing "!PYEXE!"
    exit /b 0
)

set "ARCHIVE=%TEMP%\avatar-cpython.tar.gz"
curl.exe -L --fail --progress-bar -o "%ARCHIVE%" "%PY_URL%" || exit /b 1

set "GOTHASH="
for /f "skip=1 delims=" %%H in ('certutil -hashfile "%ARCHIVE%" SHA256') do if not defined GOTHASH set "GOTHASH=%%H"
set "GOTHASH=!GOTHASH: =!"
if /i not "!GOTHASH!"=="%PY_SHA%" (
    echo checksum mismatch, refusing to use the download
    echo   expected %PY_SHA%
    echo   got      !GOTHASH!
    del "%ARCHIVE%" >nul 2>&1
    exit /b 1
)

if not exist "%RUNTIME%" mkdir "%RUNTIME%"
set "TAR=%SystemRoot%\System32\tar.exe"
if not exist "!TAR!" (
    echo "!TAR!" is missing, cannot unpack
    exit /b 1
)
"!TAR!" -xf "%ARCHIVE%" -C "%RUNTIME%" || exit /b 1
del "%ARCHIVE%" >nul 2>&1

if not exist "%RUNTIME%\python\python.exe" (
    echo the archive did not contain python\python.exe
    exit /b 1
)
set "PYEXE=%RUNTIME%\python\python.exe"
exit /b 0


:usage
echo(
echo usage: setup.bat [--force] [--run] [--venv PATH] [--branch NAME]
echo(
echo   --force        rebuild the environment from scratch
echo   --run          start the avatar once it is installed
echo   --venv PATH    where to put it ^(default .venv beside this script^)
echo   --branch NAME  which branch to install from ^(default master^)
exit /b 2


:fail
echo(
echo setup failed
exit /b 1
