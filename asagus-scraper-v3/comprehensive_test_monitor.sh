#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BASE_URL="http://localhost:8000"
MONITOR_FILE="$SCRIPT_DIR/live_monitor.log"
RESULTS_FILE="$SCRIPT_DIR/comprehensive_test_results.txt"
JOB_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs"
DOWNLOAD_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download"

# Clear previous logs
> $MONITOR_FILE
> $RESULTS_FILE

echo "========================================" | tee -a $RESULTS_FILE
echo "COMPREHENSIVE ASAGUS TEST WITH FULL MONITORING" | tee -a $RESULTS_FILE
echo "Started: $(date)" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Function to monitor everything
monitor_all_processes() {
    local JOB_ID=$1
    local CHECK_NUM=$2
    local ELAPSED=$3
    
    echo "════════════════════════════════════════" >> $MONITOR_FILE
    echo "[Monitor Check #$CHECK_NUM @ ${ELAPSED}s] - $(date +%H:%M:%S)" >> $MONITOR_FILE
    echo "════════════════════════════════════════" >> $MONITOR_FILE
    
    # 1. Job API Status
    echo "" >> $MONITOR_FILE
    echo ">>> JOB API STATUS:" >> $MONITOR_FILE
    JOB_STATUS=$(curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null)
    if [ -n "$JOB_STATUS" ]; then
        STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('status', 'unknown'))" 2>/dev/null)
        PROCESSED=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('processed_targets', 0))" 2>/dev/null)
        RECORDS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('records_found', 0))" 2>/dev/null)
        MSG=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('progress_message', 'N/A'))" 2>/dev/null)
        
        echo "  Status: $STATUS" >> $MONITOR_FILE
        echo "  Processed: $PROCESSED targets" >> $MONITOR_FILE
        echo "  Records: $RECORDS found" >> $MONITOR_FILE
        echo "  Message: $MSG" >> $MONITOR_FILE
    fi
    
    # 2. Backend Processes
    echo "" >> $MONITOR_FILE
    echo ">>> BACKEND PROCESSES:" >> $MONITOR_FILE
    ps aux | grep -E "uvicorn|asagus" | grep -v grep >> $MONITOR_FILE 2>&1 || echo "  No backend processes found" >> $MONITOR_FILE
    
    # 3. External Download Tools Status
    echo "" >> $MONITOR_FILE
    echo ">>> EXTERNAL DOWNLOAD TOOLS (from Download folder):" >> $MONITOR_FILE
    
    # Check for tool launcher processes
    LAUNCHER_PROCS=$(ps aux | grep "asagus_tool_launcher.py" | grep -v grep | wc -l)
    echo "  Tool Launcher Processes: $LAUNCHER_PROCS" >> $MONITOR_FILE
    
    if [ $LAUNCHER_PROCS -gt 0 ]; then
        echo "  Active Tools:" >> $MONITOR_FILE
        ps aux | grep "asagus_tool_launcher.py" | grep -v grep | awk '{print "    - PID "$2" : "$NF}' >> $MONITOR_FILE 2>&1
    fi
    
    # Check for specific tool processes
    echo "" >> $MONITOR_FILE
    echo "  Individual Tool Processes:" >> $MONITOR_FILE
    
    for tool in "agent-reach" "scrapegraph" "scrapling" "firecrawl" "maxun" "outreach" "scrapy" "whatsapp"; do
        TOOL_COUNT=$(ps aux | grep -i "$tool" | grep -v grep | grep -v "asagus_tool_launcher" | wc -l)
        if [ $TOOL_COUNT -gt 0 ]; then
            echo "    ✓ $tool: $TOOL_COUNT processes" >> $MONITOR_FILE
        else
            echo "    ○ $tool: idle" >> $MONITOR_FILE
        fi
    done
    
    # 4. Job Directory Files
    echo "" >> $MONITOR_FILE
    echo ">>> JOB DIRECTORY STATUS:" >> $MONITOR_FILE
    if [ -d "$JOB_DIR/$JOB_ID" ]; then
        FILE_COUNT=$(find "$JOB_DIR/$JOB_ID" -type f 2>/dev/null | wc -l)
        TOTAL_SIZE=$(du -sh "$JOB_DIR/$JOB_ID" 2>/dev/null | awk '{print $1}')
        echo "  Total Files: $FILE_COUNT" >> $MONITOR_FILE
        echo "  Total Size: $TOTAL_SIZE" >> $MONITOR_FILE
        echo "  Latest 5 files:" >> $MONITOR_FILE
        ls -lth "$JOB_DIR/$JOB_ID" 2>/dev/null | head -6 | tail -5 | awk '{print "    "$9" ("$5")"}' >> $MONITOR_FILE 2>&1
    else
        echo "  Job directory not yet created" >> $MONITOR_FILE
    fi
    
    # 5. Internal Tools Activity (from asagus-scraper-v3/backend)
    echo "" >> $MONITOR_FILE
    echo ">>> INTERNAL TOOLS & MODULES:" >> $MONITOR_FILE
    
    # Check Python processes related to internal modules
    echo "  Core Modules:" >> $MONITOR_FILE
    for module in "crawler" "extractor" "policy" "fetch" "browser" "network"; do
        MOD_COUNT=$(ps aux | grep -E "python.*$module" | grep -v grep | wc -l)
        if [ $MOD_COUNT -gt 0 ]; then
            echo "    ✓ $module: active" >> $MONITOR_FILE
        fi
    done
    
    # 6. Browser Processes
    echo "" >> $MONITOR_FILE
    echo ">>> BROWSER ENGINES:" >> $MONITOR_FILE
    for browser in "chromium" "firefox" "camoufox" "playwright" "nodriver"; do
        BROWSER_COUNT=$(ps aux | grep -i "$browser" | grep -v grep | wc -l)
        if [ $BROWSER_COUNT -gt 0 ]; then
            echo "  ✓ $browser: $BROWSER_COUNT instances" >> $MONITOR_FILE
        fi
    done
    
    # 7. Network Activity
    echo "" >> $MONITOR_FILE
    echo ">>> NETWORK CONNECTIONS:" >> $MONITOR_FILE
    ESTABLISHED=$(netstat -an 2>/dev/null | grep ESTABLISHED | grep ":8000" | wc -l)
    echo "  Backend Connections: $ESTABLISHED" >> $MONITOR_FILE
    
    # 8. Runtime Data Files
    echo "" >> $MONITOR_FILE
    echo ">>> RUNTIME DATA FILES:" >> $MONITOR_FILE
    if [ -f "data/runtime_jobs.json" ]; then
        JOBS_SIZE=$(stat -f%z "data/runtime_jobs.json" 2>/dev/null || stat -c%s "data/runtime_jobs.json" 2>/dev/null || echo "0")
        echo "  runtime_jobs.json: ${JOBS_SIZE} bytes" >> $MONITOR_FILE
    fi
    if [ -f "data/runtime_records.json" ]; then
        RECORDS_SIZE=$(stat -f%z "data/runtime_records.json" 2>/dev/null || stat -c%s "data/runtime_records.json" 2>/dev/null || echo "0")
        echo "  runtime_records.json: ${RECORDS_SIZE} bytes" >> $MONITOR_FILE
    fi
    if [ -f "data/runtime_events.json" ]; then
        EVENTS_SIZE=$(stat -f%z "data/runtime_events.json" 2>/dev/null || stat -c%s "data/runtime_events.json" 2>/dev/null || echo "0")
        echo "  runtime_events.json: ${EVENTS_SIZE} bytes" >> $MONITOR_FILE
    fi
    
    # 9. Raw HTML Archives
    echo "" >> $MONITOR_FILE
    echo ">>> RAW HTML ARCHIVES:" >> $MONITOR_FILE
    if [ -d "data/raw_html/$JOB_ID" ]; then
        HTML_COUNT=$(find "data/raw_html/$JOB_ID" -name "*.html" 2>/dev/null | wc -l)
        JSON_COUNT=$(find "data/raw_html/$JOB_ID" -name "*.json" 2>/dev/null | wc -l)
        echo "  HTML files: $HTML_COUNT" >> $MONITOR_FILE
        echo "  Metadata files: $JSON_COUNT" >> $MONITOR_FILE
    else
        echo "  No archives yet" >> $MONITOR_FILE
    fi
    
    # 10. Latest Backend Errors
    echo "" >> $MONITOR_FILE
    echo ">>> LATEST BACKEND LOG (last 3 lines):" >> $MONITOR_FILE
    if [ -f "backend-server.err" ]; then
        tail -3 backend-server.err >> $MONITOR_FILE 2>&1 || echo "  No errors" >> $MONITOR_FILE
    else
        echo "  No error log" >> $MONITOR_FILE
    fi
    
    # 11. CPU and Memory Usage
    echo "" >> $MONITOR_FILE
    echo ">>> RESOURCE USAGE:" >> $MONITOR_FILE
    TOTAL_CPU=$(ps aux | grep -E "python|chromium|firefox" | grep -v grep | awk '{sum+=$3} END {print sum}')
    TOTAL_MEM=$(ps aux | grep -E "python|chromium|firefox" | grep -v grep | awk '{sum+=$4} END {print sum}')
    echo "  Total CPU: ${TOTAL_CPU}%" >> $MONITOR_FILE
    echo "  Total Memory: ${TOTAL_MEM}%" >> $MONITOR_FILE
    
    echo "" >> $MONITOR_FILE
    echo "════════════════════════════════════════" >> $MONITOR_FILE
    echo "" >> $MONITOR_FILE
}

# Step 1: Ensure backend is running
echo "[1/5] Checking backend status..." | tee -a $RESULTS_FILE
if ! curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✗ Backend not running. Starting it..." | tee -a $RESULTS_FILE
    cd backend
    nohup python3 -m uvicorn asagus.api.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID" | tee -a $RESULTS_FILE
    cd ..
    
    # Wait for backend
    for i in {1..30}; do
        sleep 2
        if curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
            echo "✓ Backend ready" | tee -a $RESULTS_FILE
            break
        fi
        if [ $i -eq 30 ]; then
            echo "✗ Backend failed to start" | tee -a $RESULTS_FILE
            exit 1
        fi
    done
else
    echo "✓ Backend already running" | tee -a $RESULTS_FILE
fi
echo "" | tee -a $RESULTS_FILE

# Step 2: Verify all external tools are available
echo "[2/5] Verifying external Download tools..." | tee -a $RESULTS_FILE
echo "Checking Download folder: $DOWNLOAD_DIR" | tee -a $RESULTS_FILE

TOOLS_FOUND=0
for tool_dir in "$DOWNLOAD_DIR"/*/; do
    if [ -d "$tool_dir" ]; then
        TOOL_NAME=$(basename "$tool_dir")
        if [[ "$TOOL_NAME" != ".asagus-runs" ]]; then
            echo "  ✓ Found: $TOOL_NAME" | tee -a $RESULTS_FILE
            ((TOOLS_FOUND++))
        fi
    fi
done

if [ -f "$DOWNLOAD_DIR/asagus_tool_launcher.py" ]; then
    echo "  ✓ Tool launcher present" | tee -a $RESULTS_FILE
else
    echo "  ✗ Tool launcher missing!" | tee -a $RESULTS_FILE
fi

echo "Total external tools available: $TOOLS_FOUND" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 3: Submit MAX mode job
echo "[3/5] Submitting MAX mode test job..." | tee -a $RESULTS_FILE
echo "Configuration:" | tee -a $RESULTS_FILE
echo "  - Query: cafe" | tee -a $RESULTS_FILE
echo "  - Location: UAE" | tee -a $RESULTS_FILE
echo "  - Limit: 10" | tee -a $RESULTS_FILE
echo "  - Mode: MAX (all tools enabled)" | tee -a $RESULTS_FILE
echo "  - Antibot: high-stealth" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

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
    echo "✗ Failed to submit job" | tee -a $RESULTS_FILE
    echo "$JOB_RESPONSE" | tee -a $RESULTS_FILE
    exit 1
fi

echo "✓ Job submitted successfully!" | tee -a $RESULTS_FILE
echo "Job ID: $JOB_ID" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 4: Monitor everything in real-time
echo "[4/5] Starting comprehensive monitoring (will run for 3 minutes)..." | tee -a $RESULTS_FILE
echo "Monitoring log: $MONITOR_FILE" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

COMPLETED=false
for i in {1..36}; do
    ELAPSED=$((i * 5))
    
    # Run comprehensive monitoring
    monitor_all_processes "$JOB_ID" "$i" "$ELAPSED"
    
    # Also show brief summary to console
    JOB_STATUS=$(curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null)
    if [ -n "$JOB_STATUS" ]; then
        STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('status', 'unknown'))" 2>/dev/null)
        PROCESSED=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('processed_targets', 0))" 2>/dev/null)
        RECORDS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('records_found', 0))" 2>/dev/null)
        
        echo "[Check $i @ ${ELAPSED}s] Status: $STATUS | Processed: $PROCESSED | Records: $RECORDS" | tee -a $RESULTS_FILE
        
        # Check if completed
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            echo "" | tee -a $RESULTS_FILE
            echo "✓ Job $STATUS at check $i" | tee -a $RESULTS_FILE
            COMPLETED=true
            break
        fi
    fi
    
    sleep 5
done

if [ "$COMPLETED" = false ]; then
    echo "⚠ Job still running after 3 minutes" | tee -a $RESULTS_FILE
fi
echo "" | tee -a $RESULTS_FILE

# Step 5: Generate final report
echo "[5/5] Generating final comprehensive report..." | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Get final job details
echo "========================================" | tee -a $RESULTS_FILE
echo "FINAL JOB STATUS" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null | python3 -m json.tool | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "FINAL RECORDS (first 5)" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/records" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
records = data.get('records', [])
print(f'Total Records: {data.get(\"count\", 0)}')
print()
for i, rec in enumerate(records[:5], 1):
    print(f'Record {i}:')
    print(f'  Name: {rec.get(\"name\", \"N/A\")}')
    print(f'  Phone: {rec.get(\"phone\", \"N/A\")}')
    print(f'  Email: {rec.get(\"email\", \"N/A\")}')
    print(f'  Website: {rec.get(\"website_url\", \"N/A\")}')
    print(f'  Source: {rec.get(\"source\", \"N/A\")}')
    print()
" | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "TOOL EXECUTION SUMMARY" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE

# Check which external tools actually ran
echo "External Tools Executed:" | tee -a $RESULTS_FILE
if [ -d "$JOB_DIR/$JOB_ID" ]; then
    for json_file in "$JOB_DIR/$JOB_ID"/*.json; do
        if [ -f "$json_file" ]; then
            TOOL_NAME=$(basename "$json_file" .json)
            FILE_SIZE=$(stat -f%z "$json_file" 2>/dev/null || stat -c%s "$json_file" 2>/dev/null || echo "0")
            echo "  ✓ $TOOL_NAME: ${FILE_SIZE} bytes" | tee -a $RESULTS_FILE
        fi
    done
else
    echo "  No tool data found" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE
echo "Internal Components Active:" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/events?job_id=$JOB_ID&limit=100" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    events = data.get('events', [])
    layers = set()
    event_types = set()
    for event in events:
        layers.add(event.get('layer', 'unknown'))
        event_types.add(event.get('event_type', 'unknown'))
    
    print('  Layers activated:', len(layers))
    for layer in sorted(layers):
        print(f'    - {layer}')
    print()
    print('  Event types:', len(event_types))
    for et in sorted(event_types):
        print(f'    - {et}')
except:
    print('  Could not parse events')
" | tee -a $RESULTS_FILE

echo "" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "TEST COMPLETION SUMMARY" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "Completed at: $(date)" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

if [ "$COMPLETED" = true ] && [ "$STATUS" = "completed" ]; then
    echo "✓✓✓ TEST PASSED ✓✓✓" | tee -a $RESULTS_FILE
    echo "All systems operational, job completed successfully" | tee -a $RESULTS_FILE
    echo "Records found: $RECORDS" | tee -a $RESULTS_FILE
else
    echo "⚠ TEST INCOMPLETE" | tee -a $RESULTS_FILE
    echo "Job status: $STATUS" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE
echo "Results saved to: $RESULTS_FILE" | tee -a $RESULTS_FILE
echo "Monitor log saved to: $MONITOR_FILE" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE
echo "View live monitoring log with: tail -f $MONITOR_FILE" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
