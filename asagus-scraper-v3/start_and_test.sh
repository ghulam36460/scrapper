#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "ASAGUS SCRAPER - PROPER STARTUP & TEST"
echo "=========================================="
echo ""

# Kill any existing backend
echo "[1] Cleaning up old processes..."
pkill -f "uvicorn.*asagus" 2>/dev/null || true
sleep 2
echo "✓ Cleanup complete"
echo ""

# Start backend with correct path
echo "[2] Starting backend server..."
cd backend

# Start backend in background
nohup .venv/bin/python -m uvicorn asagus.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
BACKEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Waiting for backend to start..."

# Wait for backend to be ready
for i in {1..15}; do
    sleep 2
    if curl -s --max-time 1 http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Backend is ready!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "✗ Backend failed to start. Check errors:"
        tail -20 ../backend-server.err
        exit 1
    fi
done

cd ..
echo ""

# Test health endpoint
echo "[3] Testing backend..."
HEALTH=$(curl -s http://localhost:8000/health)
echo "Health check: $HEALTH"
echo ""

# Submit test job
echo "[4] Submitting test job (cafe in UAE, MAX mode)..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cafe",
    "location": "UAE",
    "limit": 10,
    "mode": "max",
    "antibot_preset": "high-stealth",
    "discovery_mode": "website_first",
    "lead_target": "businesses",
    "llm_enabled": true,
    "archive_raw_html": true,
    "enable_network_fetch": true,
    "enable_search_discovery": true
  }')

JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo "✗ Failed to submit job"
    echo "Response: $JOB_RESPONSE"
    exit 1
fi

echo "✓ Job submitted: $JOB_ID"
echo ""

# Monitor job
echo "[5] Monitoring job progress (2 minutes)..."
echo "================================================"
echo ""

for i in {1..24}; do
    sleep 5
    
    # Get job status
    JOB_DATA=$(curl -s "http://localhost:8000/api/jobs/$JOB_ID")
    STATUS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('status','?'))" 2>/dev/null)
    PROCESSED=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('processed_targets',0))" 2>/dev/null)
    RECORDS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('records_found',0))" 2>/dev/null)
    MSG=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('progress_message',''))" 2>/dev/null)
    
    echo "[$(printf '%02d' $i) @ $((i*5))s] Status: $STATUS | Processed: $PROCESSED | Records: $RECORDS"
    echo "            Message: $MSG"
    
    # Check tool processes
    TOOL_PROCS=$(ps aux | grep "tool_launcher" | grep -v grep | wc -l)
    BROWSER_PROCS=$(ps aux | grep -E "chromium|firefox|playwright" | grep -v grep | wc -l)
    echo "            Tools: $TOOL_PROCS running | Browsers: $BROWSER_PROCS active"
    echo ""
    
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo "✓ Job $STATUS!"
        break
    fi
done

echo ""
echo "================================================"
echo "[6] Final Results"
echo "================================================"
echo ""

# Get final job status
echo ">>> Job Status:"
curl -s "http://localhost:8000/api/jobs/$JOB_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
job = data.get('job', {})
print(f\"  ID: {job.get('id')}\")
print(f\"  Status: {job.get('status')}\")
print(f\"  Query: {job.get('query')} in {job.get('location')}\")
print(f\"  Mode: {job.get('mode')}\")
print(f\"  Processed: {job.get('processed_targets')}\")
print(f\"  Records Found: {job.get('records_found')}\")
print(f\"  Error: {job.get('error', 'None')}\")
"
echo ""

# Get records
echo ">>> Records (first 3):"
curl -s "http://localhost:8000/api/records" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  Total: {data.get('count', 0)} records\")
print()
for i, rec in enumerate(data.get('records', [])[:3], 1):
    print(f\"  Record {i}:\")
    print(f\"    Name: {rec.get('name')}\")
    print(f\"    Phone: {rec.get('phone')}\")
    print(f\"    Email: {rec.get('email')}\")
    print(f\"    Website: {rec.get('website_url')}\")
    print(f\"    Source: {rec.get('source')}\")
    print()
"

# Check external tools
echo ">>> External Tools Executed:"
JOB_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs/$JOB_ID"
if [ -d "$JOB_DIR" ]; then
    ls -lh "$JOB_DIR"/*.json 2>/dev/null | awk '{print "  ✓ " $9 " (" $5 ")"}'
else
    echo "  No tool data yet"
fi
echo ""

# Check layers
echo ">>> Active Layers:"
curl -s "http://localhost:8000/api/events?job_id=$JOB_ID&limit=50" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    layers = set(e.get('layer') for e in data.get('events', []))
    for layer in sorted(layers):
        print(f'  ✓ {layer}')
except:
    print('  Could not retrieve layers')
"

echo ""
echo "=========================================="
echo "TEST COMPLETE"
echo "=========================================="
echo ""
echo "Backend PID: $BACKEND_PID"
echo "Backend logs: backend-server.out, backend-server.err"
echo "Job ID: $JOB_ID"
echo ""
echo "To stop backend: kill $BACKEND_PID"
echo "To view logs: tail -f backend-server.err"
echo "=========================================="
