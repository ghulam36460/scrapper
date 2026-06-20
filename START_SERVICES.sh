#!/bin/bash
# Start Backend and Frontend for ASAGUS Scraper v3

set -e

BACKEND_DIR="asagus-scraper-v3/backend"
FRONTEND_DIR="asagus-scraper-v3/frontend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Starting ASAGUS Scraper v3 - Backend & Frontend${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo

# Stop any existing processes
echo -e "${YELLOW}Stopping any running services...${NC}"
pkill -f "uvicorn asagus.main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Stopped existing services${NC}"
echo

# Start Backend
echo -e "${BLUE}Starting Backend...${NC}"
cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

echo "Starting uvicorn server on http://127.0.0.1:8000"
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
cd - > /dev/null

echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
echo "  URL: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Logs: $BACKEND_DIR/backend.log"
echo

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is ready!${NC}"
        break
    fi
    sleep 1
    echo -n "."
done
echo

# Start Frontend
echo -e "${BLUE}Starting Frontend...${NC}"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠ Node modules not found. Installing...${NC}"
    npm install
fi

# Clean and rebuild .next directory if needed
if [ ! -d ".next" ]; then
    echo -e "${YELLOW}⚠ Building Next.js for first run...${NC}"
    rm -rf .next
fi

echo "Starting Next.js dev server on http://localhost:3000"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
cd - > /dev/null

echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
echo "  URL: http://localhost:3000"
echo "  Logs: $FRONTEND_DIR/frontend.log"
echo

# Wait for frontend to start
echo -e "${YELLOW}Waiting for frontend to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Frontend is ready!${NC}"
        break
    fi
    sleep 1
    echo -n "."
done
echo

# Summary
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ All services started successfully!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo
echo -e "${GREEN}Backend:${NC}"
echo "  URL: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  PID: $BACKEND_PID"
echo "  Logs: tail -f $BACKEND_DIR/backend.log"
echo
echo -e "${GREEN}Frontend:${NC}"
echo "  URL: http://localhost:3000"
echo "  PID: $FRONTEND_PID"
echo "  Logs: tail -f $FRONTEND_DIR/frontend.log"
echo
echo -e "${YELLOW}To stop services:${NC}"
echo "  ./STOP_SERVICES.sh"
echo "  OR: kill $BACKEND_PID $FRONTEND_PID"
echo
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
