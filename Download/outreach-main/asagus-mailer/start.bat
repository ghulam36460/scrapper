@echo off
echo ==========================================
echo  ASAGUS Mailer v2.0 - Starting...
echo ==========================================

:: Start backend
echo [1/2] Starting FastAPI backend on port 8000...
start "ASAGUS Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

:: Start frontend
echo [2/2] Starting Next.js frontend on port 3000...
start "ASAGUS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ==========================================
echo  ASAGUS Mailer is starting!
echo  Frontend: http://localhost:3000
echo  API Docs: http://localhost:8000/docs
echo ==========================================
echo.
echo Press any key to open the browser...
pause >nul

:: Open browser
start http://localhost:3000
