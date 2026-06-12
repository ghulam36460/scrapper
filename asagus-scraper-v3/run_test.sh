#!/bin/bash

BASE_URL="http://localhost:8000"
OUTPUT_FILE="/home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/test_results.json"

echo "=== Starting Cafe Scraping Test in UAE with MAX mode and HIGH-STEALTH ===" > $OUTPUT_FILE
echo "Timestamp: $(date)" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

# Submit the job
echo "Submitting job..." | tee -a $OUTPUT_FILE
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

echo "Job submission response:" | tee -a $OUTPUT_FILE
echo "$JOB_RESPONSE" | python3 -m json.tool >> $OUTPUT_FILE 2>&1

# Extract job ID
JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)

if [ -z "$JOB_ID" ]; then
    echo "ERROR: Failed to get job ID" | tee -a $OUTPUT_FILE
    exit 1
fi

echo "" >> $OUTPUT_FILE
echo "Job ID: $JOB_ID" | tee -a $OUTPUT_FILE
echo "" >> $OUTPUT_FILE

# Monitor the job for 60 seconds
echo "Monitoring job progress..." | tee -a $OUTPUT_FILE
for i in {1..12}; do
    sleep 5
    echo "--- Check $i (${i}x5 seconds) ---" >> $OUTPUT_FILE
    
    JOB_STATUS=$(curl -s "$BASE_URL/api/jobs/$JOB_ID")
    
    # Extract key fields
    STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('status', 'unknown'))" 2>/dev/null)
    PROGRESS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); job=data.get('job', {}); print(f\"Processed: {job.get('processed_targets', 0)}, Records: {job.get('records_found', 0)}, Message: {job.get('progress_message', '')}\")" 2>/dev/null)
    ERROR=$(echo "$JOB_STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('job', {}).get('error', ''))" 2>/dev/null)
    
    echo "Status: $STATUS" >> $OUTPUT_FILE
    echo "Progress: $PROGRESS" >> $OUTPUT_FILE
    if [ -n "$ERROR" ] && [ "$ERROR" != "" ]; then
        echo "Error: $ERROR" >> $OUTPUT_FILE
    fi
    echo "" >> $OUTPUT_FILE
    
    # Check if job completed or failed
    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        echo "Job $STATUS!" | tee -a $OUTPUT_FILE
        break
    fi
done

# Get final job details
echo "" >> $OUTPUT_FILE
echo "=== FINAL JOB STATUS ===" >> $OUTPUT_FILE
curl -s "$BASE_URL/api/jobs/$JOB_ID" | python3 -m json.tool >> $OUTPUT_FILE 2>&1

# Get all records
echo "" >> $OUTPUT_FILE
echo "=== SCRAPED RECORDS ===" >> $OUTPUT_FILE
curl -s "$BASE_URL/api/records" | python3 -m json.tool >> $OUTPUT_FILE 2>&1

# Check backend logs for errors
echo "" >> $OUTPUT_FILE
echo "=== BACKEND ERROR LOGS (last 50 lines) ===" >> $OUTPUT_FILE
tail -50 /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend-server.err >> $OUTPUT_FILE 2>&1

echo "" | tee -a $OUTPUT_FILE
echo "Test completed! Results saved to: $OUTPUT_FILE" | tee -a $OUTPUT_FILE
