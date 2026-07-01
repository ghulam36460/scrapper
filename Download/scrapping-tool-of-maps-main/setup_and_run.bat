@echo off
REM ============================================================
REM  Google Maps Lead Scraper - Windows Setup ^& Run
REM ------------------------------------------------------------
REM  Double-click this file, or run from a terminal:
REM     setup_and_run.bat
REM
REM  What it does:
REM    1. Locates Python (py launcher or python on PATH)
REM    2. Creates a .venv virtual environment (if missing)
REM    3. Upgrades pip / setuptools / wheel
REM    4. Installs all dependencies from requirements.txt
REM    5. Installs the Playwright Chromium browser
REM    6. Creates the output folders
REM    7. Launches the server on http://127.0.0.1:5001
REM
REM  Optional:
REM    set APP_PORT=8080 ^&^& setup_and_run.bat   (custom port)
REM    setup_and_run.bat --run-only               (skip install)
REM    setup_and_run.bat --setup-only             (install, no run)
REM ============================================================

setlocal EnableExtensions EnableDelayedExpansion

REM ---- Always work from the folder this script lives in ------
cd /d "%~dp0"

REM ---- Configurable defaults ---------------------------------
if not defined APP_PORT set "APP_PORT=5001"
if not defined APP_HOST set "APP_HOST=127.0.0.1"
set "VENV_DIR=.venv"

REM ---- Parse flags -------------------------------------------
set "DO_SETUP=1"
set "DO_RUN=1"
if /I "%~1"=="--run-only"   set "DO_SETUP=0"
if /I "%~1"=="--setup-only" set "DO_RUN=0"
if /I "%~1"=="--help"  goto :usage
if /I "%~1"=="-h"      goto :usage
if /I "%~1"=="/?"      goto :usage

echo.
echo ============================================================
echo    Google Maps Lead Scraper -- Windows Setup ^& Run
echo ============================================================
echo.

REM ============================================================
REM  LOCATE PYTHON
REM ============================================================
set "PYLAUNCHER="
where py >nul 2>&1 && set "PYLAUNCHER=py -3"
if not defined PYLAUNCHER (
    where python >nul 2>&1 && set "PYLAUNCHER=python"
)
if not defined PYLAUNCHER (
    echo [ERROR] Python was not found on your system.
    echo         Please install Python 3.9+ from https://www.python.org/downloads/
    echo         During install, tick "Add Python to PATH".
    goto :fail
)
echo [INFO] Using Python launcher: %PYLAUNCHER%
%PYLAUNCHER% --version

REM ============================================================
REM  SETUP PHASE
REM ============================================================
if "%DO_SETUP%"=="1" (

    if not exist "%VENV_DIR%\Scripts\python.exe" (
        echo [INFO] Creating virtual environment in .\%VENV_DIR% ...
        %PYLAUNCHER% -m venv "%VENV_DIR%"
        if errorlevel 1 (
            echo [ERROR] Failed to create the virtual environment.
            goto :fail
        )
        echo [OK]   Virtual environment created.
    ) else (
        echo [INFO] Virtual environment already exists -- skipping creation.
    )

    set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

    echo [INFO] Upgrading pip, setuptools, wheel ...
    "!VENV_PY!" -m pip install --upgrade pip setuptools wheel
    if errorlevel 1 (
        echo [ERROR] Failed to upgrade pip.
        goto :fail
    )

    echo [INFO] Installing Python dependencies from requirements.txt ...
    "!VENV_PY!" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        goto :fail
    )
    echo [OK]   Python dependencies installed.

    echo [INFO] Installing Playwright Chromium browser ^(this can take a while^) ...
    "!VENV_PY!" -m playwright install chromium
    if errorlevel 1 (
        echo [WARN] Playwright Chromium install reported an error.
        echo        You can retry manually: "!VENV_PY!" -m playwright install chromium
    ) else (
        echo [OK]   Playwright Chromium installed.
    )

    if not exist "output\history\searches" (
        mkdir "output\history\searches" >nul 2>&1
    )
    echo [OK]   Output directories ready.

    echo.
    echo [OK]   ===== Setup complete! =====
    echo.
)

REM ============================================================
REM  RUN PHASE
REM ============================================================
if "%DO_RUN%"=="1" (

    set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
    if not exist "!VENV_PY!" (
        echo [ERROR] Virtual environment not found.
        echo         Run without --run-only first to set it up.
        goto :fail
    )
    if not exist "backend\app.py" (
        echo [ERROR] backend\app.py not found. Run this from the project root.
        goto :fail
    )

    echo.
    echo ============================================================
    echo   Starting server on http://%APP_HOST%:%APP_PORT%
    echo   Open that URL in your browser.
    echo   Press Ctrl+C to stop.
    echo ============================================================
    echo.

    pushd backend
    "..\%VENV_DIR%\Scripts\python.exe" app.py
    popd
)

echo.
echo Done.
endlocal
exit /b 0

REM ============================================================
:usage
echo Usage: setup_and_run.bat [--setup-only ^| --run-only]
echo   --setup-only   Install dependencies and browser, then exit.
echo   --run-only     Skip install, launch the server directly.
echo.
echo Environment variables:
echo   APP_PORT   Port to listen on  ^(default: 5001^)
echo   APP_HOST   Host to bind       ^(default: 127.0.0.1^)
endlocal
exit /b 0

REM ============================================================
:fail
echo.
echo [ERROR] Setup/run failed. See messages above.
echo.
pause
endlocal
exit /b 1
