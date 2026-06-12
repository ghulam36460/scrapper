#!/bin/bash

echo "========================================"
echo "  ASAGUS Mailer v2.0 - Starting..."
echo "========================================"
echo ""

# Check if .env exists, if not create it
if [ ! -f ".env" ]; then
    echo "[INFO] No .env file found. Creating one..."
    python3 -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); f = open('.env', 'w'); f.write(f'SECRET_KEY={key}\n'); f.close(); print('[OK] Generated SECRET_KEY and saved to .env')"
    echo ""
fi

echo "[1/3] Starting Backend (FastAPI)..."
cd asagus-mailer/backend
gnome-terminal -- bash -c "uvicorn main:app --reload --host 0.0.0.0 --port 8000; exec bash" 2>/dev/null || \
xterm -e "uvicorn main:app --reload --host 0.0.0.0 --port 8000" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd \"'$(pwd)'\" && uvicorn main:app --reload --host 0.0.0.0 --port 8000"' 2>/dev/null &
cd ../..

sleep 3

echo "[2/3] Starting Frontend (Next.js)..."
cd asagus-mailer/frontend
gnome-terminal -- bash -c "npm run dev; exec bash" 2>/dev/null || \
xterm -e "npm run dev" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd \"'$(pwd)'\" && npm run dev"' 2>/dev/null &
cd ../..

echo ""
echo "========================================"
echo "  ASAGUS Mailer Started Successfully!"
echo "========================================"
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Opening frontend in browser..."

sleep 2

# Open browser
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:3000
elif command -v open > /dev/null; then
    open http://localhost:3000
fi

echo ""
echo "To stop: Close both terminal windows or press Ctrl+C"
echo ""
