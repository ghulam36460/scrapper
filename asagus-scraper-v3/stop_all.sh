#!/bin/bash

echo "Stopping ASAGUS Scraper..."

# Stop using saved PIDs
if [ -f backend.pid ]; then
    kill $(cat backend.pid) 2>/dev/null
    rm backend.pid
fi

if [ -f frontend.pid ]; then
    kill $(cat frontend.pid) 2>/dev/null
    rm frontend.pid
fi

# Force kill if still running
lsof -i :8000 2>/dev/null | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
lsof -i :3000 2>/dev/null | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null

echo "✅ All processes stopped"
