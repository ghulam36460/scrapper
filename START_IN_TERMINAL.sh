#!/bin/bash
# Start Backend and Frontend with visible output in terminals

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Starting ASAGUS Scraper v3 in Terminals${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo

# Stop any existing
echo -e "${YELLOW}Stopping any running services...${NC}"
pkill -f "uvicorn asagus.main:app" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

echo -e "${GREEN}Starting backend in new terminal...${NC}"
gnome-terminal -- bash -c "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend && echo 'Starting Backend on http://localhost:8000' && .venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload; exec bash" 2>/dev/null || \
xterm -e "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend && echo 'Starting Backend on http://localhost:8000' && .venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload; exec bash" 2>/dev/null || \
konsole -e "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend && echo 'Starting Backend on http://localhost:8000' && .venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload; exec bash" 2>/dev/null || \
echo -e "${YELLOW}Could not open terminal. Use START_SERVICES.sh instead.${NC}"

sleep 2

echo -e "${GREEN}Starting frontend in new terminal...${NC}"
gnome-terminal -- bash -c "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/frontend && echo 'Starting Frontend on http://localhost:3000' && rm -rf .next && npm run dev; exec bash" 2>/dev/null || \
xterm -e "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/frontend && echo 'Starting Frontend on http://localhost:3000' && rm -rf .next && npm run dev; exec bash" 2>/dev/null || \
konsole -e "cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/frontend && echo 'Starting Frontend on http://localhost:3000' && rm -rf .next && npm run dev; exec bash" 2>/dev/null || \
echo -e "${YELLOW}Could not open terminal. Use START_SERVICES.sh instead.${NC}"

echo
echo -e "${GREEN}✓ Services starting in separate terminals${NC}"
echo
echo -e "${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
echo
echo -e "${YELLOW}To stop: Close the terminal windows or use ./STOP_SERVICES.sh${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
