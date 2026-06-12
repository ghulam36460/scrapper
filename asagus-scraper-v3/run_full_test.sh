#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BASE_URL="http://localhost:8000"
RESULTS_FILE="$SCRIPT_DIR/full_monitoring_results.txt"
MONITOR_FILE="$SCRIPT_DIR/live_monitoring.log"

# Clear logs
> $RESULTS_FILE
> $MONITOR_FILE

echo "========================================" | tee $RESULTS_FILE
echo "FULL SYSTEM TEST - ALL TOOLS MONITORING" | tee -a $RESULTS_FILE  
echo "Started: $(date)" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Check backend
echo "[Step 1] Backend Status" | tee -a $RESULTS_FILE
if curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✓ Backend running" | tee -a $RESULTS_FILE
else
    echo "✗ Backend not running - starting it..." | tee -a $RESULTS_FILE
    cd backend
    nohup python3 -m uvicorn asagus.api.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
    sleep 10
    cd ..
    if curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
        echo "✓ Backend started" | tee -a $RESULTS_FILE
    else
        echo "✗ Backend failed to start" | tee -a $RESULTS_FILE
        exit 1
    fi
fi
echo "" | tee -a $RESULTS_FILE

# Submit job
echo "[Step 2] Submitting MAX Mode Job" | tee -a $RESULTS_FILE
JOB_RESPONSE=$(curl -s -X POST $BASE_URL/api/jobs \
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
    echo "✗ Failed to get job ID" | tee -a $RESULTS_FILE
    exit 1
fi

echo "✓ Job ID: $JOB_ID" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Monitor function
monitor_iteration() {
    local CHECK_NUM=$1
    local ELAPSED=$2
    
    echo "════════════════════════════════════════" | tee -a $MONITOR_FILE
    echo "[Check #$CHECK_NUM @ ${ELAPSED}s] $(date +%H:%M:%S)" | tee -a $MONITOR_FILE
    echo "════════════════════════════════════════" | tee -a $MONITOR_FILE
    
    # Job status from API
    JOB_DATA=$(curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null)
    STATUS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('status','?'))" 2>/dev/null)
    PROCESSED=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('processed_targets',0))" 2>/dev/null)
    RECORDS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('records_found',0))" 2>/dev/null)
    MSG=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('progress_message',''))" 2>/dev/null)
    
    echo "Job Status: $STATUS | Processed: $PROCESSED | Records: $RECORDS" | tee -a $MONITOR_FILE
    echo "Message: $MSG" | tee -a $MONITOR_FILE
    echo "" | tee -a $MONITOR_FILE
    
    # Running processes
    echo ">>> Python/Tool Processes:" | tee -a $MONITOR_FILE
    PYTHON_PROCS=$(ps aux | grep -E "python.*asagus|tool_launcher" | grep -v grep | wc -l)
    echo "  Total: $PYTHON_PROCS processes" | tee -a $MONITOR_FILE
    
    LAUNCHER_PROCS=$(ps aux | grep "tool_launcher.py" | grep -v grep | wc -l)
    if [ $LAUNCHER_PROCS -gt 0 ]; then
        echo "  ✓ Tool launchers running: $LAUNCHER_PROCS" | tee -a $MONITOR_FILE
    fi
    echo "" | tee -a $MONITOR_FILE
    
    # Browser processes
    echo ">>> Browser Processes:" | tee -a $MONITOR_FILE
    for browser in chromium firefox camoufox playwright; do
        COUNT=$(ps aux | grep -i "$browser" | grep -v grep | wc -l)
        if [ $COUNT -gt 0 ]; then
            echo "  ✓ $browser: $COUNT" | tee -a $MONITOR_FILE
        fi
    done
    echo "" | tee -a $MONITOR_FILE
    
    # Job directory
    JOB_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs/$JOB_ID"
    if [ -d "$JOB_DIR" ]; then
        FILES=$(ls -1 "$JOB_DIR" 2>/dev/null | wc -l)
        SIZE=$(du -sh "$JOB_DIR" 2>/dev/null | awk '{print $1}')
        echo ">>> Job Directory:" | tee -a $MONITOR_FILE
        echo "  Files: $FILES | Size: $SIZE" | tee -a $MONITOR_FILE
        echo "  Contents:" | tee -a $MONITOR_FILE
        ls -lh "$JOB_DIR" 2>/dev/null | tail -10 | awk '{print "    "$9" ("$5")"}' | tee -a $MONITOR_FILE
    else
        echo ">>> Job Directory: Not created yet" | tee -a $MONITOR_FILE
    fi
    echo "" | tee -a $MONITOR_FILE
    
    # Raw HTML archives
    HTML_DIR="data/raw_html/$JOB_ID"
    if [ -d "$HTML_DIR" ]; then
        HTML_COUNT=$(find "$HTML_DIR" -name "*.html" 2>/dev/null | wc -l)
        JSON_COUNT=$(find "$HTML_DIR" -name "*.json" 2>/dev/null | wc -l)
        echo ">>> HTML Archives:" | tee -a $MONITOR_FILE
        echo "  HTML files: $HTML_COUNT | Metadata: $JSON_COUNT" | tee -a $MONITOR_FILE
    fi
    echo "" | tee -a $MONITOR_FILE
    
    # Latest error (if any)
    if [ -f "backend-server.err" ]; then
        LAST_ERROR=$(tail -1 backend-server.err 2>/dev/null)
        if [ -n "$LAST_ERROR" ]; then
            echo ">>> Latest Log: $LAST_ERROR" | tee -a $MONITOR_FILE
        fi
    fi
    echo "" | tee -a $MONITOR_FILE
    
    # Return status for loop control
    echo "$STATUS"
}

# Start monitoring
echo "[Step 3] Monitoring Job Progress (3 minutes max)" | tee -a $RESULTS_FILE
echo "Monitor log: $MONITOR_FILE" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

COMPLETED=false
FINAL_STATUS="unknown"

for i in {1..36}; do
    ELAPSED=$((i * 5))
    
    # Run monitoring
    CURRENT_STATUS=$(monitor_iteration $i $ELAPSED)
    
    # Show brief summary
    echo "[Check $i @ ${ELAPSED}s] Status: $CURRENT_STATUS" | tee -a $RESULTS_FILE
    
    # Check completion
    if [ "$CURRENT_STATUS" = "completed" ] || [ "$CURRENT_STATUS" = "failed" ]; then
        FINAL_STATUS="$CURRENT_STATUS"
        COMPLETED=true
        echo "✓ Job $CURRENT_STATUS!" | tee -a $RESULTS_FILE
        break
    fi
    
    sleep 5
done

if [ "$COMPLETED" = false ]; then
    echo "⚠ Job still running after 3 minutes" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE

# Final results
echo "[Step 4] Collecting Final Results" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

echo ">>> Final Job Data:" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/jobs/$JOB_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
job = data.get('job', {})
print(f\"  Status: {job.get('status')}\")
print(f\"  Processed: {job.get('processed_targets')}\")
print(f\"  Records: {job.get('records_found')}\")
print(f\"  Error: {job.get('error', 'None')}\")
" | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE

echo ">>> Records Sample:" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/records" | python3 -c "
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
    print()
" | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE

echo ">>> External Tools Executed:" | tee -a $RESULTS_FILE
JOB_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs/$JOB_ID"
if [ -d "$JOB_DIR" ]; then
    ls -lh "$JOB_DIR" | grep "\.json$" | awk '{print "  ✓ " $9 " (" $5 ")"}' | tee -a $RESULTS_FILE
else
    echo "  No tool data" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE

echo ">>> Internal Layers Activated:" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/events?job_id=$JOB_ID&limit=100" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    layers = set(e.get('layer') for e in data.get('events', []))
    for layer in sorted(layers):
        print(f'  ✓ {layer}')
except:
    print('  Could not retrieve events')
" | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "TEST COMPLETE" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "Completed: $(date)" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

if [ "$FINAL_STATUS" = "completed" ]; then
    echo "✓✓✓ SUCCESS ✓✓✓" | tee -a $RESULTS_FILE
else
    echo "Status: $FINAL_STATUS" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE
echo "Full results: $RESULTS_FILE" | tee -a $RESULTS_FILE
echo "Monitor log: $MONITOR_FILE" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
