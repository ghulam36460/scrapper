@echo off
echo ========================================
echo   ASAGUS Mailer v2.0 - Starting...
echo ========================================
echo.

REM Check if .env exists, if not create it
if not exist ".env" (
    echo [INFO] No .env file found. Creating one...
    python -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); f = open('.env', 'w'); f.write(f'SECRET_KEY={key}\n'); f.close(); print(f'[OK] Generated SECRET_KEY and saved to .env')"
    echo.
)

echo [1/3] Starting Backend (FastAPI)...
cd asagus-mailer\backend
start "ASAGUS Backend" cmd /k "uvicorn main:app --reload --host 0.0.0.0 --port 8000"
cd ..\..

timeout /t 3 /nobreak >nul

echo [2/3] Starting Frontend (Next.js)...
cd asagus-mailer\frontend
start "ASAGUS Frontend" cmd /k "npm run dev"
cd ..\..

echo.
echo ========================================
echo   ASAGUS Mailer Started Successfully!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to open frontend in browser...
pause >nul

start http://localhost:3000

echo.
echo To stop: Close both terminal windows
echo.
