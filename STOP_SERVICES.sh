#!/bin/bash
# Stop Backend and Frontend for ASAGUS Scraper v3

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Stopping ASAGUS Scraper v3 - Backend & Frontend${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo

# Stop backend
echo -e "${YELLOW}Stopping backend...${NC}"
BACKEND_PIDS=$(pgrep -f "uvicorn asagus.main:app")
if [ -n "$BACKEND_PIDS" ]; then
    pkill -f "uvicorn asagus.main:app"
    echo -e "${GREEN}✓ Backend stopped (PIDs: $BACKEND_PIDS)${NC}"
else
    echo "No backend process found"
fi

# Stop frontend
echo -e "${YELLOW}Stopping frontend...${NC}"
FRONTEND_PIDS=$(pgrep -f "npm run dev")
if [ -n "$FRONTEND_PIDS" ]; then
    pkill -f "npm run dev"
    echo -e "${GREEN}✓ Frontend stopped (PIDs: $FRONTEND_PIDS)${NC}"
fi

NEXT_PIDS=$(pgrep -f "next dev")
if [ -n "$NEXT_PIDS" ]; then
    pkill -f "next dev"
    echo -e "${GREEN}✓ Next.js stopped (PIDs: $NEXT_PIDS)${NC}"
fi

VITE_PIDS=$(pgrep -f "vite")
if [ -n "$VITE_PIDS" ]; then
    pkill -f "vite"
    echo -e "${GREEN}✓ Vite stopped (PIDs: $VITE_PIDS)${NC}"
fi

if [ -z "$FRONTEND_PIDS" ] && [ -z "$VITE_PIDS" ] && [ -z "$NEXT_PIDS" ]; then
    echo "No frontend process found"
fi

sleep 1

# Verify all stopped
REMAINING=$(ps aux | grep -E "uvicorn|npm run dev|next dev|vite" | grep -v grep | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo
    echo -e "${GREEN}✓ All services stopped successfully!${NC}"
else
    echo
    echo -e "${YELLOW}⚠ Some processes may still be running:${NC}"
    ps aux | grep -E "uvicorn|npm run dev|next dev|vite" | grep -v grep
fi

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
