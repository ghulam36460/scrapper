@echo off
title ASAGUS Mailer - Startup
color 0A

echo.
echo ================================================
echo          ASAGUS MAILER v2.0 - STARTUP
echo ================================================
echo.

REM Kill existing processes
echo [Step 1/4] Cleaning up ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing process on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Killing process on port 3000...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo Done.
echo.

echo [Step 2/4] Starting Backend Server...
cd asagus-mailer\backend
start "ASAGUS Backend - Port 8000" cmd /k "python -m uvicorn main:app --host 127.0.0.1 --port 8000"
cd ..\..
echo Backend starting on http://localhost:8000
echo.

echo [Step 3/4] Waiting for backend to initialize...
timeout /t 8 /nobreak >nul
echo.

echo [Step 4/4] Starting Frontend Server...
cd asagus-mailer\frontend
start "ASAGUS Frontend - Port 3000" cmd /k "npm run dev"
cd ..\..
echo Frontend starting on http://localhost:3000
echo.

echo ================================================
echo          STARTUP COMPLETE
echo ================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Waiting 10 seconds before opening browser...
timeout /t 10 /nobreak >nul

echo Opening browser...
start http://localhost:3000

echo.
echo ================================================
echo Both servers are running in separate windows.
echo Close those windows to stop the servers.
echo ================================================
echo.
pause
