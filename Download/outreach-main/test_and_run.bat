@echo off
echo ========================================
echo   ASAGUS Mailer v2.0 - Test System
echo ========================================
echo.

REM Kill any existing processes on ports 8000 and 3000
echo [1/5] Cleaning up existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

REM Check if .env exists, if not create it
if not exist ".env" (
    echo [2/5] Creating .env file...
    python -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); f = open('.env', 'w'); f.write(f'SECRET_KEY={key}\n'); f.close(); print('[OK] Generated SECRET_KEY')"
    echo.
) else (
    echo [2/5] .env file exists
)

echo [3/5] Starting Backend...
cd asagus-mailer\backend
start "ASAGUS Backend" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
cd ..\..

echo [4/5] Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo [5/5] Running System Tests...
echo.
cd asagus-mailer\backend
python test_system.py
set TEST_RESULT=%ERRORLEVEL%
cd ..\..

echo.
if %TEST_RESULT%==0 (
    echo ========================================
    echo   Backend Tests: PASSED
    echo ========================================
    echo.
    echo Starting Frontend...
    cd asagus-mailer\frontend
    start "ASAGUS Frontend" cmd /k "npm run dev"
    cd ..\..
    
    timeout /t 5 /nobreak >nul
    
    echo.
    echo ========================================
    echo   ASAGUS Mailer Started Successfully!
    echo ========================================
    echo.
    echo Backend:  http://localhost:8000
    echo Frontend: http://localhost:3000
    echo API Docs: http://localhost:8000/docs
    echo.
    echo Opening frontend in browser...
    timeout /t 3 /nobreak >nul
    start http://localhost:3000
    echo.
    echo System is running. Press any key to exit...
    pause >nul
) else (
    echo ========================================
    echo   Backend Tests: FAILED
    echo ========================================
    echo.
    echo Please check the error messages above.
    echo Backend is still running for debugging.
    echo.
    pause
)
