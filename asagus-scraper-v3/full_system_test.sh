#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

BASE_URL="http://localhost:8000"
RESULTS_FILE="$SCRIPT_DIR/full_test_results.txt"
JOB_DIR="/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs"

echo "========================================" | tee $RESULTS_FILE
echo "ASAGUS SCRAPER FULL SYSTEM TEST" | tee -a $RESULTS_FILE
echo "Started: $(date)" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 1: Check if backend is running
echo "[1/6] Checking backend status..." | tee -a $RESULTS_FILE
if curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✓ Backend is running" | tee -a $RESULTS_FILE
else
    echo "✗ Backend is NOT running. Starting it now..." | tee -a $RESULTS_FILE
    cd backend
    nohup python3 -m uvicorn asagus.api.main:app --host 0.0.0.0 --port 8000 > ../backend-server.out 2> ../backend-server.err &
    BACKEND_PID=$!
    echo "Backend started with PID: $BACKEND_PID" | tee -a $RESULTS_FILE
    cd ..
    
    # Wait for backend to start
    echo "Waiting for backend to be ready..." | tee -a $RESULTS_FILE
    for i in {1..30}; do
        sleep 2
        if curl -s --max-time 3 "$BASE_URL/health" > /dev/null 2>&1; then
            echo "✓ Backend is now running" | tee -a $RESULTS_FILE
            break
        fi
        if [ $i -eq 30 ]; then
            echo "✗ Backend failed to start. Check backend-server.err" | tee -a $RESULTS_FILE
            tail -20 backend-server.err | tee -a $RESULTS_FILE
            exit 1
        fi
    done
fi
echo "" | tee -a $RESULTS_FILE

# Step 2: Clear old job data
echo "[2/6] Cleaning up old test data..." | tee -a $RESULTS_FILE
rm -f data/runtime_*.json 2>/dev/null || true
echo "✓ Old data cleared" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 3: Submit test job
echo "[3/6] Submitting test job: Cafes in UAE with MAX mode + HIGH-STEALTH..." | tee -a $RESULTS_FILE
JOB_RESPONSE=$(curl -s -X POST $BASE_URL/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cafe",
    "location": "UAE",
    "limit": 5,
    "mode": "max",
    "antibot_preset": "high-stealth",
    "discovery_mode": "website_first",
    "lead_target": "businesses",
    "llm_enabled": true,
    "archive_raw_html": true,
    "enable_network_fetch": true,
    "enable_search_discovery": true
  }')

echo "$JOB_RESPONSE" | python3 -m json.tool | tee -a $RESULTS_FILE

JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo "✗ ERROR: Failed to get job ID" | tee -a $RESULTS_FILE
    echo "Response was: $JOB_RESPONSE" | tee -a $RESULTS_FILE
    exit 1
fi

echo "" | tee -a $RESULTS_FILE
echo "✓ Job submitted successfully!" | tee -a $RESULTS_FILE
echo "Job ID: $JOB_ID" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 4: Monitor job with detailed logging
echo "[4/6] Monitoring job progress (will check for 3 minutes)..." | tee -a $RESULTS_FILE
echo "Job directory: $JOB_DIR/$JOB_ID" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

COMPLETED=false
for i in {1..36}; do
    sleep 5
    
    # Get job status from API
    JOB_STATUS=$(curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null)
    
    if [ -n "$JOB_STATUS" ]; then
        STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('status', 'unknown'))" 2>/dev/null)
        PROCESSED=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('processed_targets', 0))" 2>/dev/null)
        RECORDS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('records_found', 0))" 2>/dev/null)
        MSG=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('progress_message', 'N/A'))" 2>/dev/null)
        ERROR_MSG=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('error', ''))" 2>/dev/null)
        
        echo "[Check $i @ $((i*5))s] Status: $STATUS | Processed: $PROCESSED | Records: $RECORDS" | tee -a $RESULTS_FILE
        echo "  Message: $MSG" | tee -a $RESULTS_FILE
        
        if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "" ] && [ "$ERROR_MSG" != "None" ]; then
            echo "  ⚠ Error: $ERROR_MSG" | tee -a $RESULTS_FILE
        fi
        
        # Check job directory for actual activity
        if [ -d "$JOB_DIR/$JOB_ID" ]; then
            FILE_COUNT=$(find "$JOB_DIR/$JOB_ID" -type f 2>/dev/null | wc -l)
            echo "  Files in job dir: $FILE_COUNT" | tee -a $RESULTS_FILE
            
            # Show latest files
            if [ $FILE_COUNT -gt 0 ]; then
                echo "  Latest files:" | tee -a $RESULTS_FILE
                ls -lth "$JOB_DIR/$JOB_ID" 2>/dev/null | head -5 | tee -a $RESULTS_FILE
            fi
        fi
        
        # Check if job completed or failed
        if [ "$STATUS" = "completed" ]; then
            echo "" | tee -a $RESULTS_FILE
            echo "✓ JOB COMPLETED!" | tee -a $RESULTS_FILE
            COMPLETED=true
            break
        elif [ "$STATUS" = "failed" ]; then
            echo "" | tee -a $RESULTS_FILE
            echo "✗ JOB FAILED!" | tee -a $RESULTS_FILE
            COMPLETED=true
            break
        fi
    else
        echo "[Check $i @ $((i*5))s] ⚠ Could not get job status from API" | tee -a $RESULTS_FILE
    fi
    
    echo "" | tee -a $RESULTS_FILE
done

if [ "$COMPLETED" = false ]; then
    echo "⚠ Job did not complete within 3 minutes" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE

# Step 5: Get final results
echo "[5/6] Retrieving final job details and records..." | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

echo "--- Final Job Status ---" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/jobs/$JOB_ID" 2>/dev/null | python3 -m json.tool | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

echo "--- All Records ---" | tee -a $RESULTS_FILE
curl -s "$BASE_URL/api/records" 2>/dev/null | python3 -m json.tool | head -100 | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Step 6: Check for errors in logs
echo "[6/6] Checking backend logs for errors..." | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

if [ -f "backend-server.err" ] && [ -s "backend-server.err" ]; then
    echo "--- Backend Error Log (last 30 lines) ---" | tee -a $RESULTS_FILE
    tail -30 backend-server.err | tee -a $RESULTS_FILE
else
    echo "✓ No errors in backend log" | tee -a $RESULTS_FILE
fi

echo "" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE
echo "TEST COMPLETED: $(date)" | tee -a $RESULTS_FILE
echo "Results saved to: $RESULTS_FILE" | tee -a $RESULTS_FILE
echo "========================================" | tee -a $RESULTS_FILE

# Show summary
echo "" | tee -a $RESULTS_FILE
echo "SUMMARY:" | tee -a $RESULTS_FILE
if [ "$COMPLETED" = true ]; then
    if [ "$STATUS" = "completed" ]; then
        echo "✓ Test PASSED - Job completed successfully with $RECORDS records" | tee -a $RESULTS_FILE
    else
        echo "✗ Test FAILED - Job failed with error" | tee -a $RESULTS_FILE
    fi
else
    echo "⚠ Test TIMEOUT - Job did not complete within time limit" | tee -a $RESULTS_FILE
fi
