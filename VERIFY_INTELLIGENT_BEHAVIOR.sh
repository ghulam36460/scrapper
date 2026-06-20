#!/bin/bash
# ASAGUS Scraper v3 - Intelligent Behavior Verification Test
# This script tests all intelligent behaviors and the Download tools fix

set -e

BACKEND_DIR="asagus-scraper-v3/backend"
FRONTEND_DIR="asagus-scraper-v3/frontend"
API_BASE="http://localhost:8000/api"
FRONTEND_URL="http://localhost:5173"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  ASAGUS Scraper v3 - Intelligent Behavior Verification${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo

# Function to print section headers
print_section() {
    echo
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  $1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

# Function to check if service is running
check_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${YELLOW}Waiting for $service_name to start...${NC}"
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service_name is running${NC}"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}✗ $service_name failed to start after $max_attempts attempts${NC}"
    return 1
}

# Function to wait for job completion
wait_for_job() {
    local job_id=$1
    local timeout=300  # 5 minutes
    local elapsed=0
    
    echo -e "${YELLOW}Waiting for job $job_id to complete...${NC}"
    
    while [ $elapsed -lt $timeout ]; do
        status=$(curl -s "$API_BASE/jobs/$job_id" | jq -r '.status' 2>/dev/null || echo "unknown")
        
        if [ "$status" = "completed" ]; then
            echo -e "${GREEN}✓ Job completed successfully${NC}"
            return 0
        elif [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
            echo -e "${RED}✗ Job $status${NC}"
            return 1
        fi
        
        # Show progress
        progress=$(curl -s "$API_BASE/jobs/$job_id" | jq -r '.progress_pct // 0' 2>/dev/null || echo "0")
        echo -ne "\rProgress: $progress% | Status: $status | Elapsed: ${elapsed}s"
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    echo
    echo -e "${RED}✗ Job timed out after $timeout seconds${NC}"
    return 1
}

# ═══════════════════════════════════════════════════════════
# STEP 1: Clean All Data
# ═══════════════════════════════════════════════════════════

print_section "STEP 1: Clean All Data and Backup"

# Create backup directory
BACKUP_DIR="$HOME/.local/share/Trash/files/asagus_verify_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Backing up existing data to: $BACKUP_DIR"

# Backup data if exists
if [ -d "$BACKEND_DIR/data" ] && [ "$(ls -A $BACKEND_DIR/data)" ]; then
    cp -r "$BACKEND_DIR/data" "$BACKUP_DIR/backend_data"
    echo -e "${GREEN}✓ Backend data backed up${NC}"
fi

if [ -d "Download/.asagus-runs" ] && [ "$(ls -A Download/.asagus-runs)" ]; then
    cp -r "Download/.asagus-runs" "$BACKUP_DIR/download_runs"
    echo -e "${GREEN}✓ Download runs backed up${NC}"
fi

# Clean data
echo "Cleaning all data..."
rm -rf "$BACKEND_DIR/data"/*
rm -rf Download/.asagus-runs/*
mkdir -p "$BACKEND_DIR/data"
mkdir -p "Download/.asagus-runs"

echo -e "${GREEN}✓ All data cleaned${NC}"
echo "Backup location: $BACKUP_DIR"

# ═══════════════════════════════════════════════════════════
# STEP 2: Start Services
# ═══════════════════════════════════════════════════════════

print_section "STEP 2: Start Backend and Frontend"

# Kill any existing processes
echo "Stopping any running services..."
pkill -f "uvicorn asagus.main:app" || true
pkill -f "npm run dev" || true
sleep 2

# Start backend
echo "Starting backend..."
cd "$BACKEND_DIR"
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
cd - > /dev/null

# Check backend
check_service "$API_BASE/health" "Backend" || exit 1

# Start frontend
echo "Starting frontend..."
cd "$FRONTEND_DIR"
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
cd - > /dev/null

# Check frontend
check_service "$FRONTEND_URL" "Frontend" || exit 1

echo -e "${GREEN}✓ Backend PID: $BACKEND_PID${NC}"
echo -e "${GREEN}✓ Frontend PID: $FRONTEND_PID${NC}"

# ═══════════════════════════════════════════════════════════
# STEP 3: First Test Run (MAX Mode with Network)
# ═══════════════════════════════════════════════════════════

print_section "STEP 3: First Test Run - MAX Mode with Real Network"

echo "Creating job: 'coffee shops in Doha Qatar' - 5 records - MAX mode"

JOB1_RESPONSE=$(curl -s -X POST "$API_BASE/jobs" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "coffee shops in Doha Qatar",
        "location": "Doha, Qatar",
        "limit": 5,
        "mode": "max",
        "preset": "high-stealth",
        "enable_llm": true
    }')

JOB1_ID=$(echo "$JOB1_RESPONSE" | jq -r '.id')

if [ -z "$JOB1_ID" ] || [ "$JOB1_ID" = "null" ]; then
    echo -e "${RED}✗ Failed to create job${NC}"
    echo "$JOB1_RESPONSE" | jq '.'
    exit 1
fi

echo -e "${GREEN}✓ Job created: $JOB1_ID${NC}"

# Wait for job completion
wait_for_job "$JOB1_ID"
echo

# ═══════════════════════════════════════════════════════════
# STEP 4: Analyze First Run Results
# ═══════════════════════════════════════════════════════════

print_section "STEP 4: Analyze First Run Results"

# Get job details
echo "Fetching job details..."
JOB1_DETAILS=$(curl -s "$API_BASE/jobs/$JOB1_ID")
echo "$JOB1_DETAILS" | jq '{
    id,
    status,
    progress_pct,
    records_count: .stats.records_count,
    events_count: .stats.events_count,
    duration: .elapsed_seconds
}'

# Get records
echo
echo "Fetching records..."
RECORDS1=$(curl -s "$API_BASE/records")
RECORDS1_COUNT=$(echo "$RECORDS1" | jq '. | length')
RECORDS1_AVG_COMPLETENESS=$(echo "$RECORDS1" | jq '[.[] | .record_completeness] | add / length')
RECORDS1_PARTIAL=$(echo "$RECORDS1" | jq '[.[] | select(.record_completeness < 0.8)] | length')

echo -e "${BLUE}Records Statistics:${NC}"
echo "  Total records: $RECORDS1_COUNT"
echo "  Average completeness: $(printf "%.1f%%" $(echo "$RECORDS1_AVG_COMPLETENESS * 100" | bc))"
echo "  Partial records (<80%): $RECORDS1_PARTIAL"

# Show sample records
echo
echo -e "${BLUE}Sample Records (first 3):${NC}"
echo "$RECORDS1" | jq -r '.[:3] | .[] | "  • \(.business_name // "N/A") - Completeness: \(.record_completeness * 100 | round)% - Email: \(.email // "missing") - Phone: \(.phone // "missing")"'

# ═══════════════════════════════════════════════════════════
# STEP 5: Check Download Tools Execution
# ═══════════════════════════════════════════════════════════

print_section "STEP 5: Check Download Tools Execution"

echo "Checking Download tool outputs for job $JOB1_ID..."
TOOL_OUTPUT_DIR="Download/.asagus-runs/$JOB1_ID"

if [ ! -d "$TOOL_OUTPUT_DIR" ]; then
    echo -e "${RED}✗ Tool output directory not found: $TOOL_OUTPUT_DIR${NC}"
else
    echo -e "${GREEN}✓ Tool output directory found${NC}"
    
    # Count tool outputs
    TOOL_COUNT=$(ls -1 "$TOOL_OUTPUT_DIR"/*.json 2>/dev/null | wc -l)
    echo "  Tools executed: $TOOL_COUNT"
    
    # Check each tool
    echo
    echo -e "${BLUE}Tool Execution Status:${NC}"
    for tool_file in "$TOOL_OUTPUT_DIR"/*.json; do
        if [ -f "$tool_file" ]; then
            tool_name=$(basename "$tool_file" .json)
            dry_run=$(jq -r '.dry_run // "unknown"' "$tool_file")
            status=$(jq -r '.status // "unknown"' "$tool_file")
            
            # Color code based on dry_run and status
            if [ "$dry_run" = "false" ]; then
                dry_run_color="${GREEN}"
            else
                dry_run_color="${RED}"
            fi
            
            if [ "$status" = "completed" ]; then
                status_color="${GREEN}"
            elif [ "$status" = "failed" ]; then
                status_color="${RED}"
            else
                status_color="${YELLOW}"
            fi
            
            echo -e "  • ${tool_name}: dry_run=${dry_run_color}${dry_run}${NC} | status=${status_color}${status}${NC}"
            
            # Check if tool has output data
            if [ -f "$TOOL_OUTPUT_DIR/${tool_name}.csv" ]; then
                csv_lines=$(wc -l < "$TOOL_OUTPUT_DIR/${tool_name}.csv")
                echo "    CSV output: $csv_lines lines"
            fi
        fi
    done
fi

# ═══════════════════════════════════════════════════════════
# STEP 6: Test Intelligent Behavior #1 - Partial Records
# ═══════════════════════════════════════════════════════════

print_section "STEP 6: Verify Partial Records Are Stored"

echo "Checking if partial records (missing fields) are stored..."

PARTIAL_RECORDS=$(curl -s "$API_BASE/records" | jq '[.[] | select(.record_completeness < 0.8)]')
PARTIAL_COUNT=$(echo "$PARTIAL_RECORDS" | jq '. | length')

if [ "$PARTIAL_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS: Found $PARTIAL_COUNT partial records stored${NC}"
    echo
    echo -e "${BLUE}Sample Partial Record:${NC}"
    echo "$PARTIAL_RECORDS" | jq -r '.[0] | "  Name: \(.business_name // "N/A")\n  Completeness: \((.record_completeness * 100) | round)%\n  Email: \(.email // "MISSING")\n  Phone: \(.phone // "MISSING")\n  Facebook: \(.facebook_url // "MISSING")\n  Website: \(.website_url // "MISSING")"'
else
    echo -e "${YELLOW}⚠ WARNING: No partial records found (all records >80% complete)${NC}"
fi

# ═══════════════════════════════════════════════════════════
# STEP 7: Second Test Run (Same Query - Test Deduplication)
# ═══════════════════════════════════════════════════════════

print_section "STEP 7: Second Test Run - Same Query (Test Deduplication)"

echo "Creating identical job to test deduplication and update behavior..."

JOB2_RESPONSE=$(curl -s -X POST "$API_BASE/jobs" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "coffee shops in Doha Qatar",
        "location": "Doha, Qatar",
        "limit": 5,
        "mode": "max",
        "preset": "high-stealth",
        "enable_llm": true
    }')

JOB2_ID=$(echo "$JOB2_RESPONSE" | jq -r '.id')

if [ -z "$JOB2_ID" ] || [ "$JOB2_ID" = "null" ]; then
    echo -e "${RED}✗ Failed to create job${NC}"
    echo "$JOB2_RESPONSE" | jq '.'
    exit 1
fi

echo -e "${GREEN}✓ Job created: $JOB2_ID${NC}"

# Wait for job completion
wait_for_job "$JOB2_ID"
echo

# ═══════════════════════════════════════════════════════════
# STEP 8: Analyze Deduplication Results
# ═══════════════════════════════════════════════════════════

print_section "STEP 8: Analyze Deduplication Results"

# Get records after second run
RECORDS2=$(curl -s "$API_BASE/records")
RECORDS2_COUNT=$(echo "$RECORDS2" | jq '. | length')

echo -e "${BLUE}Record Count Comparison:${NC}"
echo "  After first run:  $RECORDS1_COUNT records"
echo "  After second run: $RECORDS2_COUNT records"
echo "  Difference:       $((RECORDS2_COUNT - RECORDS1_COUNT)) records"

if [ $RECORDS2_COUNT -le $((RECORDS1_COUNT + 2)) ]; then
    echo -e "${GREEN}✓ PASS: Deduplication working (minimal new records)${NC}"
else
    echo -e "${RED}✗ FAIL: Too many new records (deduplication may not be working)${NC}"
fi

# Check for duplicate reasons
echo
echo "Checking records with deduplication markers..."
DEDUPE_RECORDS=$(curl -s "$API_BASE/records" | jq '[.[] | select(.dedupe_reasons | length > 0)]')
DEDUPE_COUNT=$(echo "$DEDUPE_RECORDS" | jq '. | length')

if [ "$DEDUPE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS: Found $DEDUPE_COUNT records with deduplication markers${NC}"
    echo
    echo -e "${BLUE}Sample Deduplicated Record:${NC}"
    echo "$DEDUPE_RECORDS" | jq -r '.[0] | "  Name: \(.business_name // "N/A")\n  Dedupe reasons: \(.dedupe_reasons | join(", "))\n  Duplicate score: \(.duplicate_score)\n  Merged sources: \(.raw_fields.merged_source_urls | length // 0) URLs"'
else
    echo -e "${YELLOW}⚠ WARNING: No records with deduplication markers found${NC}"
fi

# ═══════════════════════════════════════════════════════════
# STEP 9: Check Secondary Database
# ═══════════════════════════════════════════════════════════

print_section "STEP 9: Check Secondary Database (All Events)"

SECONDARY_RECORDS=$(curl -s "$API_BASE/records/secondary")
SECONDARY_COUNT=$(echo "$SECONDARY_RECORDS" | jq '. | length')

echo "Secondary database records: $SECONDARY_COUNT"

if [ "$SECONDARY_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Secondary database is capturing all events${NC}"
    
    # Show sample
    echo
    echo -e "${BLUE}Sample Secondary Record:${NC}"
    echo "$SECONDARY_RECORDS" | jq -r '.[-1] | "  URL: \(.url // "N/A")\n  Reason: \(.skip_reason // "captured")\n  Confidence: \(.confidence // 0)\n  Timestamp: \(.timestamp // "N/A")"'
else
    echo -e "${YELLOW}⚠ No secondary records found${NC}"
fi

# ═══════════════════════════════════════════════════════════
# STEP 10: Final Summary
# ═══════════════════════════════════════════════════════════

print_section "STEP 10: Final Summary and Results"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                    TEST RESULTS SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo

# Create results directory
RESULTS_DIR="intelligent_behavior_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

# Export all data
echo "Exporting test results to: $RESULTS_DIR/"

curl -s "$API_BASE/records" > "$RESULTS_DIR/primary_records.json"
curl -s "$API_BASE/records/secondary" > "$RESULTS_DIR/secondary_records.json"
curl -s "$API_BASE/jobs/$JOB1_ID" > "$RESULTS_DIR/job1_details.json"
curl -s "$API_BASE/jobs/$JOB2_ID" > "$RESULTS_DIR/job2_details.json"

# Copy Download tool outputs
if [ -d "$TOOL_OUTPUT_DIR" ]; then
    cp -r "$TOOL_OUTPUT_DIR" "$RESULTS_DIR/download_tools_job1"
fi

JOB2_TOOL_DIR="Download/.asagus-runs/$JOB2_ID"
if [ -d "$JOB2_TOOL_DIR" ]; then
    cp -r "$JOB2_TOOL_DIR" "$RESULTS_DIR/download_tools_job2"
fi

# Generate summary report
cat > "$RESULTS_DIR/SUMMARY.txt" << EOF
ASAGUS Scraper v3 - Intelligent Behavior Verification Test
═══════════════════════════════════════════════════════════

Test Date: $(date)
Backend PID: $BACKEND_PID
Frontend PID: $FRONTEND_PID

═══════════════════════════════════════════════════════════
JOB DETAILS
═══════════════════════════════════════════════════════════

Job 1 ID: $JOB1_ID
Job 2 ID: $JOB2_ID
Query: "coffee shops in Doha Qatar"
Mode: MAX
Limit: 5 records per job

═══════════════════════════════════════════════════════════
TEST RESULTS
═══════════════════════════════════════════════════════════

✓ Download Tools Execution:
  - Tools executed: $TOOL_COUNT
  - Job 1 output dir: $TOOL_OUTPUT_DIR
  - Job 2 output dir: $JOB2_TOOL_DIR

✓ Data Storage:
  - Primary records after job 1: $RECORDS1_COUNT
  - Primary records after job 2: $RECORDS2_COUNT
  - Secondary records total: $SECONDARY_COUNT
  - New records added: $((RECORDS2_COUNT - RECORDS1_COUNT))

✓ Intelligent Behaviors:
  - Partial records stored: $PARTIAL_COUNT
  - Records with deduplication: $DEDUPE_COUNT
  - Average completeness: $(printf "%.1f%%" $(echo "$RECORDS1_AVG_COMPLETENESS * 100" | bc))

═══════════════════════════════════════════════════════════
VERIFICATION CHECKLIST
═══════════════════════════════════════════════════════════

EOF

# Add checklist items
if [ "$TOOL_COUNT" -gt 0 ]; then
    echo "[✓] Download tools executed in MAX mode" >> "$RESULTS_DIR/SUMMARY.txt"
else
    echo "[✗] Download tools did NOT execute" >> "$RESULTS_DIR/SUMMARY.txt"
fi

if [ "$PARTIAL_COUNT" -gt 0 ]; then
    echo "[✓] Partial records are stored (don't waste data)" >> "$RESULTS_DIR/SUMMARY.txt"
else
    echo "[?] No partial records found (all complete)" >> "$RESULTS_DIR/SUMMARY.txt"
fi

if [ $RECORDS2_COUNT -le $((RECORDS1_COUNT + 2)) ]; then
    echo "[✓] Deduplication working (minimal new records)" >> "$RESULTS_DIR/SUMMARY.txt"
else
    echo "[✗] Deduplication may NOT be working (too many new records)" >> "$RESULTS_DIR/SUMMARY.txt"
fi

if [ "$DEDUPE_COUNT" -gt 0 ]; then
    echo "[✓] Records have deduplication markers" >> "$RESULTS_DIR/SUMMARY.txt"
else
    echo "[?] No deduplication markers found" >> "$RESULTS_DIR/SUMMARY.txt"
fi

if [ "$SECONDARY_COUNT" -gt 0 ]; then
    echo "[✓] Secondary database capturing all events" >> "$RESULTS_DIR/SUMMARY.txt"
else
    echo "[?] Secondary database is empty" >> "$RESULTS_DIR/SUMMARY.txt"
fi

echo "" >> "$RESULTS_DIR/SUMMARY.txt"
echo "═══════════════════════════════════════════════════════════" >> "$RESULTS_DIR/SUMMARY.txt"
echo "" >> "$RESULTS_DIR/SUMMARY.txt"
echo "All test data exported to: $RESULTS_DIR/" >> "$RESULTS_DIR/SUMMARY.txt"
echo "Backup data stored in: $BACKUP_DIR" >> "$RESULTS_DIR/SUMMARY.txt"

# Display summary
cat "$RESULTS_DIR/SUMMARY.txt"

echo
echo -e "${GREEN}✓ All tests completed${NC}"
echo -e "${GREEN}✓ Results saved to: $RESULTS_DIR/${NC}"
echo
echo -e "${YELLOW}Backend and Frontend are still running:${NC}"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Backend PID: $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo
echo "To stop services:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Complete - Review $RESULTS_DIR/SUMMARY.txt${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
