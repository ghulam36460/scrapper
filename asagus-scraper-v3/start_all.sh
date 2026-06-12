#!/bin/bash

echo "═══════════════════════════════════════════════════════"
echo "  ASAGUS SCRAPER - START SCRIPT"
echo "═══════════════════════════════════════════════════════"
echo ""

# Kill any existing processes
echo "1. Cleaning up old processes..."
lsof -i :8000 2>/dev/null | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
lsof -i :3000 2>/dev/null | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
sleep 1
echo "   ✅ Cleanup complete"
echo ""

# Start backend
echo "2. Starting Backend..."
cd backend
nohup .venv/bin/python -m uvicorn asagus.main:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend started (PID: $BACKEND_PID)"
echo "   📝 Logs: tail -f backend.log"
cd ..
sleep 3

# Check backend health
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend is healthy"
else
    echo "   ⚠️  Backend not responding yet (may take a few more seconds)"
fi
echo ""

# Start frontend
echo "3. Starting Frontend..."
cd frontend
nohup npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   ✅ Frontend started (PID: $FRONTEND_PID)"
echo "   📝 Logs: tail -f frontend.log"
cd ..
sleep 5

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ SYSTEM STARTED!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📡 Backend:  http://localhost:8000"
echo "🌐 Frontend: http://localhost:3000"
echo "🌐 Network:  http://192.168.1.14:3000 (or your local IP)"
echo ""
echo "📊 CSV Export: Go to Records tab → Click 'Export CSV'"
echo ""
echo "📝 View logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "🛑 To stop:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo "   OR: ./stop_all.sh"
echo ""
echo "Process IDs saved to:"
echo "   Backend:  $BACKEND_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""

# Save PIDs for easy stopping
echo $BACKEND_PID > backend.pid
echo $FRONTEND_PID > frontend.pid

echo "✨ Ready! Open http://localhost:3000 in your browser"
echo ""
