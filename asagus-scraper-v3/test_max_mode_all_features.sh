#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

TEST_LOG="$SCRIPT_DIR/max_mode_full_test.log"
> $TEST_LOG

echo "========================================" | tee $TEST_LOG
echo "MAX MODE COMPREHENSIVE TEST" | tee -a $TEST_LOG
echo "Testing ALL Components & Tools" | tee -a $TEST_LOG
echo "$(date)" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Kill existing backend
echo "[Setup] Stopping any running backend..." | tee -a $TEST_LOG
pkill -f "uvicorn.*asagus" 2>/dev/null || true
sleep 3
echo "✓ Cleanup done" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Start backend
echo "[1] Starting Backend..." | tee -a $TEST_LOG
cd backend
nohup .venv/bin/python -m uvicorn asagus.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
BACKEND_PID=$!
cd ..
echo "Backend PID: $BACKEND_PID" | tee -a $TEST_LOG

# Wait for ready
for i in {1..20}; do
    sleep 2
    if curl -s --max-time 1 http://localhost:8000/api/jobs > /dev/null 2>&1; then
        echo "✓ Backend ready!" | tee -a $TEST_LOG
        break
    fi
    if [ $i -eq 20 ]; then
        echo "✗ Backend failed to start" | tee -a $TEST_LOG
        tail -20 backend-server.err | tee -a $TEST_LOG
        exit 1
    fi
done
echo "" | tee -a $TEST_LOG

# Verify Download tools
echo "[2] Verifying External Download Tools..." | tee -a $TEST_LOG
DOWNLOAD_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download"

if [ -d "$DOWNLOAD_DIR" ]; then
    echo "Download directory: $DOWNLOAD_DIR" | tee -a $TEST_LOG
    TOOL_COUNT=0
    for tool_dir in "$DOWNLOAD_DIR"/*-main/; do
        if [ -d "$tool_dir" ]; then
            TOOL_NAME=$(basename "$tool_dir")
            echo "  ✓ $TOOL_NAME" | tee -a $TEST_LOG
            ((TOOL_COUNT++))
        fi
    done
    echo "Total tools found: $TOOL_COUNT" | tee -a $TEST_LOG
    
    if [ -f "$DOWNLOAD_DIR/asagus_tool_launcher.py" ]; then
        echo "  ✓ Tool launcher exists" | tee -a $TEST_LOG
        # Check if it's executable
        head -5 "$DOWNLOAD_DIR/asagus_tool_launcher.py" | grep -q "python" && echo "  ✓ Launcher looks valid" | tee -a $TEST_LOG
    else
        echo "  ✗ Tool launcher MISSING!" | tee -a $TEST_LOG
    fi
else
    echo "✗ Download directory NOT FOUND!" | tee -a $TEST_LOG
fi
echo "" | tee -a $TEST_LOG

# Submit MAX mode job with ALL features enabled
echo "[3] Submitting MAX Mode Job with ALL Features..." | tee -a $TEST_LOG
echo "Configuration:" | tee -a $TEST_LOG
echo "  - Mode: MAX" | tee -a $TEST_LOG
echo "  - Antibot: high-stealth (ultra stealth)" | tee -a $TEST_LOG
echo "  - Query: restaurant" | tee -a $TEST_LOG
echo "  - Location: Dubai, UAE" | tee -a $TEST_LOG
echo "  - Limit: 15 targets" | tee -a $TEST_LOG
echo "  - LLM: Enabled" | tee -a $TEST_LOG
echo "  - Social profiles: Enabled" | tee -a $TEST_LOG
echo "  - Network fetch: Enabled" | tee -a $TEST_LOG
echo "  - Search discovery: Enabled" | tee -a $TEST_LOG
echo "  - Archive HTML: Enabled" | tee -a $TEST_LOG
echo "  - DOM fingerprint: Enabled" | tee -a $TEST_LOG
echo "  - Social auth: Facebook + Instagram" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restaurant",
    "location": "Dubai, UAE",
    "limit": 15,
    "mode": "max",
    "antibot_preset": "high-stealth",
    "discovery_mode": "website_first",
    "lead_target": "businesses",
    "website_filter": "any",
    "decision_maker_titles": "owner, founder, CEO, manager",
    "llm_enabled": true,
    "archive_raw_html": true,
    "capture_dom_fingerprint": true,
    "capture_device_stamp": true,
    "manual_review_on_challenge": true,
    "enable_network_fetch": true,
    "enable_search_discovery": true,
    "include_social_profiles": true,
    "social_auth_mode": "public",
    "social_auth_platforms": ["facebook", "instagram"],
    "social_auth_required": false,
    "store_partial_records": true,
    "max_browser_actions": 10,
    "max_seconds_per_page": 30
  }')

echo "Job Response:" | tee -a $TEST_LOG
echo "$JOB_RESPONSE" | python3 -m json.tool | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo "✗ Failed to get job ID!" | tee -a $TEST_LOG
    exit 1
fi

echo "✓ Job ID: $JOB_ID" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Check job events to see what features activated
echo "[4] Checking Job Initialization Events..." | tee -a $TEST_LOG
sleep 3
curl -s "http://localhost:8000/api/events?job_id=$JOB_ID&limit=20" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    events = data.get('events', [])
    print(f'Events logged: {len(events)}')
    print()
    for event in events[-10:]:
        layer = event.get('layer', '?')
        etype = event.get('event_type', '?')
        msg = event.get('message', '')
        print(f'  [{layer}] {etype}: {msg}')
except Exception as e:
    print(f'Error: {e}')
" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Monitor with detailed component checking
echo "[5] Monitoring Job Progress (3 minutes)..." | tee -a $TEST_LOG
echo "Checking ALL components every 10 seconds" | tee -a $TEST_LOG
echo "================================================" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

JOB_DIR="$DOWNLOAD_DIR/.asagus-runs/$JOB_ID"

for i in {1..18}; do
    ELAPSED=$((i * 10))
    
    echo "──────────────────────────────────────────────" | tee -a $TEST_LOG
    echo "[Check $i @ ${ELAPSED}s] $(date +%H:%M:%S)" | tee -a $TEST_LOG
    echo "──────────────────────────────────────────────" | tee -a $TEST_LOG
    
    # Job status
    JOB_DATA=$(curl -s "http://localhost:8000/api/jobs/$JOB_ID" 2>/dev/null)
    STATUS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('status','?'))" 2>/dev/null)
    PROCESSED=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('processed_targets',0))" 2>/dev/null)
    RECORDS=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('records_found',0))" 2>/dev/null)
    MSG=$(echo "$JOB_DATA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('job',{}).get('progress_message',''))" 2>/dev/null)
    
    echo "Job: $STATUS | Processed: $PROCESSED | Records: $RECORDS" | tee -a $TEST_LOG
    echo "Message: $MSG" | tee -a $TEST_LOG
    echo "" | tee -a $TEST_LOG
    
    # Check Download tool processes
    echo ">>> Download Tool Processes:" | tee -a $TEST_LOG
    LAUNCHER_COUNT=$(ps aux | grep "tool_launcher.py" | grep -v grep | wc -l)
    echo "  Tool launchers: $LAUNCHER_COUNT" | tee -a $TEST_LOG
    
    if [ $LAUNCHER_COUNT -gt 0 ]; then
        ps aux | grep "tool_launcher.py" | grep -v grep | awk '{print "    PID " $2 ": " $(NF-3) " " $(NF-2) " " $(NF-1) " " $NF}' | head -5 | tee -a $TEST_LOG
    else
        echo "    ⚠ No tool launchers found!" | tee -a $TEST_LOG
    fi
    echo "" | tee -a $TEST_LOG
    
    # Check for specific Download tool processes
    echo ">>> Specific Tools Running:" | tee -a $TEST_LOG
    for tool in "agent-reach" "scrapegraph" "scrapling" "firecrawl" "maxun" "scrapy" "outreach"; do
        COUNT=$(ps aux | grep -i "$tool" | grep -v grep | grep -v "tool_launcher" | wc -l)
        if [ $COUNT -gt 0 ]; then
            echo "  ✓ $tool: $COUNT processes" | tee -a $TEST_LOG
        fi
    done
    echo "" | tee -a $TEST_LOG
    
    # Check browser processes
    echo ">>> Browser Processes:" | tee -a $TEST_LOG
    CHROME=$(ps aux | grep -E "chromium|chrome" | grep -v grep | wc -l)
    FIREFOX=$(ps aux | grep firefox | grep -v grep | wc -l)
    PLAYWRIGHT=$(ps aux | grep playwright | grep -v grep | wc -l)
    echo "  Chromium/Chrome: $CHROME" | tee -a $TEST_LOG
    echo "  Firefox: $FIREFOX" | tee -a $TEST_LOG
    echo "  Playwright: $PLAYWRIGHT" | tee -a $TEST_LOG
    echo "  Total browsers: $((CHROME + FIREFOX + PLAYWRIGHT))" | tee -a $TEST_LOG
    echo "" | tee -a $TEST_LOG
    
    # Check job directory
    if [ -d "$JOB_DIR" ]; then
        FILE_COUNT=$(ls -1 "$JOB_DIR" 2>/dev/null | wc -l)
        echo ">>> Job Directory ($JOB_DIR):" | tee -a $TEST_LOG
        echo "  Files: $FILE_COUNT" | tee -a $TEST_LOG
        if [ $FILE_COUNT -gt 0 ]; then
            echo "  Contents:" | tee -a $TEST_LOG
            ls -lh "$JOB_DIR" 2>/dev/null | tail -10 | awk '{print "    " $9 " (" $5 ")"}' | tee -a $TEST_LOG
        fi
    else
        echo ">>> Job Directory: Not created yet" | tee -a $TEST_LOG
    fi
    echo "" | tee -a $TEST_LOG
    
    # Check HTML archives
    HTML_DIR="data/raw_html/$JOB_ID"
    if [ -d "$HTML_DIR" ]; then
        HTML_COUNT=$(find "$HTML_DIR" -name "*.html" 2>/dev/null | wc -l)
        JSON_COUNT=$(find "$HTML_DIR" -name "*.json" 2>/dev/null | wc -l)
        echo ">>> HTML Archives:" | tee -a $TEST_LOG
        echo "  HTML files: $HTML_COUNT" | tee -a $TEST_LOG
        echo "  Metadata files: $JSON_COUNT" | tee -a $TEST_LOG
    fi
    echo "" | tee -a $TEST_LOG
    
    # Check recent events
    echo ">>> Recent Events (last 3):" | tee -a $TEST_LOG
    curl -s "http://localhost:8000/api/events?job_id=$JOB_ID&limit=3" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for event in data.get('events', [])[:3]:
        print(f\"  [{event.get('layer')}] {event.get('event_type')}: {event.get('message')}\")
except:
    pass
" | tee -a $TEST_LOG
    echo "" | tee -a $TEST_LOG
    
    # Check for errors
    if [ -f "backend-server.err" ]; then
        LAST_ERROR=$(tail -1 backend-server.err 2>/dev/null)
        if [ -n "$LAST_ERROR" ]; then
            echo ">>> Latest Backend Log:" | tee -a $TEST_LOG
            echo "  $LAST_ERROR" | tee -a $TEST_LOG
            echo "" | tee -a $TEST_LOG
        fi
    fi
    
    # Check completion
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo "✓ Job $STATUS!" | tee -a $TEST_LOG
        break
    fi
    
    sleep 10
done

echo "" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
echo "[6] FINAL RESULTS ANALYSIS" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Final job status
echo ">>> Final Job Status:" | tee -a $TEST_LOG
curl -s "http://localhost:8000/api/jobs/$JOB_ID" | python3 -c "
import sys, json
data = json.load(sys.stdin)
job = data.get('job', {})
print(f\"  Status: {job.get('status')}\")
print(f\"  Mode: {job.get('mode')}\")
print(f\"  Query: {job.get('query')} in {job.get('location')}\")
print(f\"  Processed: {job.get('processed_targets')}\")
print(f\"  Records: {job.get('records_found')}\")
print(f\"  Started: {job.get('started_at')}\")
print(f\"  Completed: {job.get('completed_at')}\")
print(f\"  Error: {job.get('error', 'None')}\")
" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Check all layers activated
echo ">>> All Layers Activated:" | tee -a $TEST_LOG
curl -s "http://localhost:8000/api/events?job_id=$JOB_ID&limit=100" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    events = data.get('events', [])
    layers = set(e.get('layer') for e in events)
    event_types = set(e.get('event_type') for e in events)
    
    print(f'  Total events: {len(events)}')
    print(f'  Layers active: {len(layers)}')
    for layer in sorted(layers):
        print(f'    ✓ {layer}')
    print()
    print(f'  Event types: {len(event_types)}')
    for et in sorted(event_types)[:10]:
        print(f'    - {et}')
except Exception as e:
    print(f'  Error: {e}')
" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Check Download tools execution
echo ">>> Download Tools Executed:" | tee -a $TEST_LOG
if [ -d "$JOB_DIR" ]; then
    TOOL_FILES=$(ls -1 "$JOB_DIR"/*.json 2>/dev/null | wc -l)
    echo "  Total tool output files: $TOOL_FILES" | tee -a $TEST_LOG
    echo "  Tools that ran:" | tee -a $TEST_LOG
    for json_file in "$JOB_DIR"/*.json 2>/dev/null; do
        if [ -f "$json_file" ]; then
            TOOL_NAME=$(basename "$json_file" .json)
            SIZE=$(stat -c%s "$json_file" 2>/dev/null || stat -f%z "$json_file" 2>/dev/null)
            echo "    ✓ $TOOL_NAME: ${SIZE} bytes" | tee -a $TEST_LOG
        fi
    done
else
    echo "  ✗ No Download tool outputs found!" | tee -a $TEST_LOG
fi
echo "" | tee -a $TEST_LOG

# Check records with social profiles
echo ">>> Records with Social Profiles:" | tee -a $TEST_LOG
curl -s "http://localhost:8000/api/records" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    records = data.get('records', [])
    print(f'  Total records: {len(records)}')
    print()
    
    social_count = 0
    for rec in records[:5]:
        has_social = rec.get('facebook_url') or rec.get('instagram_url') or rec.get('twitter_url') or rec.get('linkedin_url')
        if has_social:
            social_count += 1
        
        print(f\"  Record: {rec.get('name', 'N/A')}\")
        print(f\"    Phone: {rec.get('phone', 'N/A')}\")
        print(f\"    Email: {rec.get('email', 'N/A')}\")
        print(f\"    Website: {rec.get('website_url', 'N/A')}\")
        print(f\"    Facebook: {rec.get('facebook_url', 'N/A')}\")
        print(f\"    Instagram: {rec.get('instagram_url', 'N/A')}\")
        print(f\"    Twitter: {rec.get('twitter_url', 'N/A')}\")
        print(f\"    LinkedIn: {rec.get('linkedin_url', 'N/A')}\")
        print(f\"    Source: {rec.get('source', 'N/A')}\")
        print()
    
    print(f'  Records with social profiles: {social_count}/{len(records)}')
except Exception as e:
    print(f'  Error: {e}')
" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Summary
echo "========================================" | tee -a $TEST_LOG
echo "TEST SUMMARY" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Verification checklist
echo "Component Verification:" | tee -a $TEST_LOG
echo "" | tee -a $TEST_LOG

# Check if Download tools ran
if [ -d "$JOB_DIR" ] && [ $(ls -1 "$JOB_DIR"/*.json 2>/dev/null | wc -l) -gt 0 ]; then
    echo "  ✓ Download tools EXECUTED" | tee -a $TEST_LOG
else
    echo "  ✗ Download tools DID NOT EXECUTE" | tee -a $TEST_LOG
fi

# Check if social profiles found
SOCIAL_CHECK=$(curl -s "http://localhost:8000/api/records" | python3 -c "
import sys, json
data = json.load(sys.stdin)
records = data.get('records', [])
social = any(r.get('facebook_url') or r.get('instagram_url') for r in records)
print('yes' if social else 'no')
" 2>/dev/null)

if [ "$SOCIAL_CHECK" = "yes" ]; then
    echo "  ✓ Social profiles FOUND" | tee -a $TEST_LOG
else
    echo "  ⚠ Social profiles NOT FOUND" | tee -a $TEST_LOG
fi

# Check if records were created
RECORD_COUNT=$(curl -s "http://localhost:8000/api/records" | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null)
if [ "$RECORD_COUNT" -gt 0 ]; then
    echo "  ✓ Records extracted: $RECORD_COUNT" | tee -a $TEST_LOG
else
    echo "  ✗ NO records extracted" | tee -a $TEST_LOG
fi

# Check if HTML archived
if [ -d "data/raw_html/$JOB_ID" ] && [ $(find "data/raw_html/$JOB_ID" -name "*.html" 2>/dev/null | wc -l) -gt 0 ]; then
    echo "  ✓ HTML archives CREATED" | tee -a $TEST_LOG
else
    echo "  ⚠ HTML archives NOT CREATED" | tee -a $TEST_LOG
fi

# Check layers
LAYER_COUNT=$(curl -s "http://localhost:8000/api/events?job_id=$JOB_ID&limit=100" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(set(e.get('layer') for e in data.get('events',[]))))" 2>/dev/null)
if [ "$LAYER_COUNT" -ge 5 ]; then
    echo "  ✓ Multiple layers active: $LAYER_COUNT" | tee -a $TEST_LOG
else
    echo "  ⚠ Few layers active: $LAYER_COUNT" | tee -a $TEST_LOG
fi

echo "" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
echo "Test completed: $(date)" | tee -a $TEST_LOG
echo "Backend PID: $BACKEND_PID" | tee -a $TEST_LOG
echo "Job ID: $JOB_ID" | tee -a $TEST_LOG
echo "Full log: $TEST_LOG" | tee -a $TEST_LOG
echo "========================================" | tee -a $TEST_LOG
