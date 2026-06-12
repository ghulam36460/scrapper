@echo off
setlocal enabledelayedexpansion
title ASAGUS Mailer v2.0 - Startup
color 0A

echo.
echo ========================================================
echo          ASAGUS MAILER v2.0 - STARTING UP
echo ========================================================
echo.

REM Step 1: Kill existing processes
echo [1/6] Cleaning up existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    if !ERRORLEVEL! EQU 0 echo   - Killed process on port 8000
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    if !ERRORLEVEL! EQU 0 echo   - Killed process on port 3000
)
timeout /t 2 /nobreak >nul
echo   Done.
echo.

REM Step 2: Check .env
echo [2/6] Checking environment...
if not exist ".env" (
    echo   Creating .env file...
    python -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); open('.env', 'w').write(f'SECRET_KEY={key}\n'); print('   SECRET_KEY generated')"
) else (
    echo   .env file exists
)
echo.

REM Step 3: Check backend dependencies
echo [3/6] Verifying backend dependencies...
cd asagus-mailer\backend
python -c "import fastapi" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   Installing backend dependencies...
    pip install -q -r requirements.txt
    echo   Done.
) else (
    echo   Dependencies OK
)
cd ..\..
echo.

REM Step 4: Check frontend dependencies
echo [4/6] Verifying frontend dependencies...
cd asagus-mailer\frontend
if not exist "node_modules\next" (
    echo   Installing frontend dependencies...
    call npm install --silent
    echo   Done.
) else (
    echo   Dependencies OK
)
cd ..\..
echo.

REM Step 5: Start Backend
echo [5/6] Starting Backend Server...
cd asagus-mailer\backend
start "ASAGUS Backend" cmd /k "title ASAGUS Backend ^& color 0B ^& python -m uvicorn main:app --host 127.0.0.1 --port 8000"
cd ..\..
echo   Backend starting at http://localhost:8000
echo   Waiting for initialization...
timeout /t 8 /nobreak >nul
echo.

REM Step 6: Start Frontend
echo [6/6] Starting Frontend Server...
cd asagus-mailer\frontend
start "ASAGUS Frontend" cmd /k "title ASAGUS Frontend ^& color 0E ^& npm run dev"
cd ..\..
echo   Frontend starting at http://localhost:3000
echo.

echo ========================================================
echo          STARTUP COMPLETE - SYSTEM RUNNING
echo ========================================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo.
echo   Waiting 12 seconds for servers to fully start...
timeout /t 12 /nobreak >nul

echo   Opening browser...
start http://localhost:3000

echo.
echo ========================================================
echo   SYSTEM IS NOW RUNNING
echo ========================================================
echo.
echo   Two server windows are open:
echo   - ASAGUS Backend (blue)
echo   - ASAGUS Frontend (yellow)
echo.
echo   To stop: Close both server windows
echo.
echo   Press any key to exit this window...
pause >nul
