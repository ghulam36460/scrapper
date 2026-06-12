#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

DIAG_FILE="$SCRIPT_DIR/diagnostic_report.txt"

echo "========================================" | tee $DIAG_FILE
echo "ASAGUS SCRAPER DIAGNOSTIC REPORT" | tee -a $DIAG_FILE
echo "$(date)" | tee -a $DIAG_FILE
echo "========================================" | tee -a $DIAG_FILE
echo "" | tee -a $DIAG_FILE

# 1. Check Backend Process
echo "[1] Backend Process Status" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
BACKEND_PROC=$(ps aux | grep "uvicorn.*asagus" | grep -v grep | wc -l)
if [ $BACKEND_PROC -gt 0 ]; then
    echo "✓ Backend process found:" | tee -a $DIAG_FILE
    ps aux | grep "uvicorn.*asagus" | grep -v grep | tee -a $DIAG_FILE
else
    echo "✗ Backend process NOT running" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 2. Check Backend Port
echo "[2] Backend Port Status" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
PORT_CHECK=$(netstat -tuln 2>/dev/null | grep ":8000" || ss -tuln 2>/dev/null | grep ":8000" || echo "Port not listening")
if [[ "$PORT_CHECK" == *"LISTEN"* ]] || [[ "$PORT_CHECK" == *"8000"* ]]; then
    echo "✓ Port 8000 is listening:" | tee -a $DIAG_FILE
    echo "$PORT_CHECK" | tee -a $DIAG_FILE
else
    echo "✗ Port 8000 is NOT listening" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 3. Test Backend Health Endpoint
echo "[3] Backend Health Endpoint" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
HEALTH_CHECK=$(curl -s --max-time 2 http://localhost:8000/health 2>&1)
if [ -n "$HEALTH_CHECK" ] && [[ "$HEALTH_CHECK" != *"Failed to connect"* ]]; then
    echo "✓ Backend responding:" | tee -a $DIAG_FILE
    echo "$HEALTH_CHECK" | tee -a $DIAG_FILE
else
    echo "✗ Backend NOT responding" | tee -a $DIAG_FILE
    echo "Error: $HEALTH_CHECK" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 4. Check Virtual Environment
echo "[4] Virtual Environment" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
if [ -d "backend/.venv" ]; then
    echo "✓ Virtual environment exists" | tee -a $DIAG_FILE
    echo "Python version:" | tee -a $DIAG_FILE
    backend/.venv/bin/python --version | tee -a $DIAG_FILE
    echo "Installed packages (key ones):" | tee -a $DIAG_FILE
    backend/.venv/bin/pip list | grep -E "fastapi|uvicorn|playwright|curl_cffi|scrapy" | tee -a $DIAG_FILE
else
    echo "✗ Virtual environment missing" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 5. Check Backend Error Logs
echo "[5] Recent Backend Errors" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
if [ -f "backend-server.err" ] && [ -s "backend-server.err" ]; then
    echo "Last 10 lines of error log:" | tee -a $DIAG_FILE
    tail -10 backend-server.err | tee -a $DIAG_FILE
else
    echo "No error log or empty" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 6. Check Data Files
echo "[6] Data Files Status" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
for file in runtime_jobs.json runtime_records.json runtime_events.json; do
    if [ -f "data/$file" ]; then
        SIZE=$(stat -c%s "data/$file" 2>/dev/null || stat -f%z "data/$file" 2>/dev/null)
        echo "  $file: ${SIZE} bytes" | tee -a $DIAG_FILE
    else
        echo "  $file: missing" | tee -a $DIAG_FILE
    fi
done
echo "" | tee -a $DIAG_FILE

# 7. Check Recent Jobs
echo "[7] Recent Jobs" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
JOBS_CHECK=$(curl -s --max-time 2 http://localhost:8000/api/jobs 2>&1)
if [ -n "$JOBS_CHECK" ] && [[ "$JOBS_CHECK" != *"Failed to connect"* ]]; then
    echo "$JOBS_CHECK" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    jobs = data.get('jobs', [])
    print(f'Total jobs: {len(jobs)}')
    for job in jobs[:3]:
        print(f\"  - {job.get('id')}: {job.get('status')} ({job.get('query')} in {job.get('location')})\")
except:
    print('Could not parse jobs')
" | tee -a $DIAG_FILE
else
    echo "Could not retrieve jobs" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 8. Check Browser Binaries
echo "[8] Browser Binaries" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
for browser in chromium firefox; do
    if command -v $browser &> /dev/null; then
        echo "✓ $browser: $(command -v $browser)" | tee -a $DIAG_FILE
    else
        echo "✗ $browser: not found" | tee -a $DIAG_FILE
    fi
done

# Check Playwright browsers
if backend/.venv/bin/python -c "from playwright.sync_api import sync_playwright; sync_playwright()" 2>/dev/null; then
    echo "✓ Playwright installed" | tee -a $DIAG_FILE
else
    echo "⚠ Playwright may not be installed" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 9. Check External Tools
echo "[9] External Tools (Download folder)" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
DOWNLOAD_DIR="../Download"
if [ -d "$DOWNLOAD_DIR" ]; then
    TOOL_COUNT=$(ls -d $DOWNLOAD_DIR/*-main 2>/dev/null | wc -l)
    echo "Found $TOOL_COUNT external tool directories:" | tee -a $DIAG_FILE
    ls -d $DOWNLOAD_DIR/*-main 2>/dev/null | xargs -n1 basename | head -5 | sed 's/^/  - /' | tee -a $DIAG_FILE
    
    if [ -f "$DOWNLOAD_DIR/asagus_tool_launcher.py" ]; then
        echo "✓ Tool launcher present" | tee -a $DIAG_FILE
    else
        echo "✗ Tool launcher missing" | tee -a $DIAG_FILE
    fi
else
    echo "✗ Download folder not found" | tee -a $DIAG_FILE
fi
echo "" | tee -a $DIAG_FILE

# 10. System Resources
echo "[10] System Resources" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE
echo "CPU Usage (Python processes):" | tee -a $DIAG_FILE
ps aux | grep python | grep -v grep | awk '{print "  " $2 " - CPU:" $3"% MEM:" $4"% - " $11}' | head -5 | tee -a $DIAG_FILE
echo "" | tee -a $DIAG_FILE
echo "Disk Space:" | tee -a $DIAG_FILE
df -h . | tee -a $DIAG_FILE
echo "" | tee -a $DIAG_FILE

# 11. Try Starting Backend if Not Running
echo "[11] Backend Restart Attempt" | tee -a $DIAG_FILE
echo "----------------------------" | tee -a $DIAG_FILE

if [ $BACKEND_PROC -eq 0 ]; then
    echo "Attempting to start backend..." | tee -a $DIAG_FILE
    cd backend
    nohup .venv/bin/python -m uvicorn asagus.api.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
    BACKEND_PID=$!
    cd ..
    
    echo "Started backend with PID: $BACKEND_PID" | tee -a $DIAG_FILE
    echo "Waiting 5 seconds for startup..." | tee -a $DIAG_FILE
    sleep 5
    
    # Check if it started
    HEALTH_RECHECK=$(curl -s --max-time 2 http://localhost:8000/health 2>&1)
    if [ -n "$HEALTH_RECHECK" ] && [[ "$HEALTH_RECHECK" != *"Failed to connect"* ]]; then
        echo "✓ Backend started successfully!" | tee -a $DIAG_FILE
        echo "$HEALTH_RECHECK" | tee -a $DIAG_FILE
    else
        echo "✗ Backend failed to start" | tee -a $DIAG_FILE
        echo "Last error log lines:" | tee -a $DIAG_FILE
        tail -5 backend-server.err | tee -a $DIAG_FILE
    fi
else
    echo "Backend already running, skipping restart" | tee -a $DIAG_FILE
fi

echo "" | tee -a $DIAG_FILE
echo "========================================" | tee -a $DIAG_FILE
echo "DIAGNOSIS COMPLETE" | tee -a $DIAG_FILE
echo "Report saved to: $DIAG_FILE" | tee -a $DIAG_FILE
echo "========================================" | tee -a $DIAG_FILE
