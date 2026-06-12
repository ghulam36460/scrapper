@echo off
title ASAGUS Mailer - Pre-Flight Check
color 0B

echo.
echo ================================================
echo     ASAGUS MAILER - PRE-FLIGHT CHECK
echo ================================================
echo.

set ERRORS=0

REM Check Python
echo [1/8] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python --version
    echo ✓ Python is installed
) else (
    echo ✗ Python is NOT installed
    set /a ERRORS+=1
)
echo.

REM Check Node.js
echo [2/8] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    node --version
    echo ✓ Node.js is installed
) else (
    echo ✗ Node.js is NOT installed
    set /a ERRORS+=1
)
echo.

REM Check .env file
echo [3/8] Checking .env file...
if exist ".env" (
    echo ✓ .env file exists
) else (
    echo ✗ .env file is missing
    echo Creating .env file...
    python -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); f = open('.env', 'w'); f.write(f'SECRET_KEY={key}\n'); f.close(); print('✓ Created .env file')"
)
echo.

REM Check backend dependencies
echo [4/8] Checking backend dependencies...
cd asagus-mailer\backend
python -c "import fastapi, uvicorn, sqlalchemy, pandas, cryptography" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✓ Backend dependencies installed
) else (
    echo ✗ Backend dependencies missing
    echo Installing...
    pip install -r requirements.txt
)
cd ..\..
echo.

REM Check frontend dependencies
echo [5/8] Checking frontend dependencies...
cd asagus-mailer\frontend
if exist "node_modules" (
    echo ✓ Frontend dependencies installed
) else (
    echo ✗ Frontend dependencies missing
    echo Installing...
    call npm install
)
cd ..\..
echo.

REM Check if ports are available
echo [6/8] Checking port 8000...
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ⚠ Port 8000 is in use (will be cleared on startup)
) else (
    echo ✓ Port 8000 is available
)
echo.

echo [7/8] Checking port 3000...
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ⚠ Port 3000 is in use (will be cleared on startup)
) else (
    echo ✓ Port 3000 is available
)
echo.

REM Check file structure
echo [8/8] Checking file structure...
if exist "asagus-mailer\backend\main.py" (
    if exist "asagus-mailer\frontend\package.json" (
        echo ✓ File structure is correct
    ) else (
        echo ✗ Frontend files missing
        set /a ERRORS+=1
    )
) else (
    echo ✗ Backend files missing
    set /a ERRORS+=1
)
echo.

echo ================================================
echo              CHECK COMPLETE
echo ================================================
echo.

if %ERRORS% EQU 0 (
    echo ✓ All checks passed! System is ready to run.
    echo.
    echo Run RUN.bat to start the system.
) else (
    echo ✗ %ERRORS% error(s) found. Please fix them before running.
)
echo.
pause
