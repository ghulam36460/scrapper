#!/bin/bash
# Kill existing backend
pkill -f "uvicorn asagus.main:app" || true
sleep 2

# Start backend
cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend
source .venv/bin/activate
nohup python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 > ../backend-server.out 2> ../backend-server.err &
echo "Backend restarted with PID: $!"
sleep 3
echo "Backend status:"
curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo "Backend not ready yet"
