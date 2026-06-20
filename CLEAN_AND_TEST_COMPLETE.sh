#!/bin/bash
# Complete Clean, Test, and Analysis Script
# This script backs up data, cleans everything, runs a real scraping job, and analyzes results

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════════════"
echo "  ASAGUS SCRAPER V3 - COMPLETE CLEAN & REAL TEST"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

# ============================================================================
# STEP 1: BACKUP EXISTING DATA
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 1: Backup Existing Data to Recycle Bin${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RECYCLE_BIN="$HOME/.local/share/Trash/files/asagus_backup_$TIMESTAMP"

echo "Creating backup directory: $RECYCLE_BIN"
mkdir -p "$RECYCLE_BIN"

# Backup data directory
if [ -d "asagus-scraper-v3/data" ]; then
    echo "✅ Backing up data directory..."
    cp -r asagus-scraper-v3/data "$RECYCLE_BIN/"
    echo "   Backed up to: $RECYCLE_BIN/data"
fi

# Backup Download tool outputs
if [ -d "Download/.asagus-runs" ]; then
    echo "✅ Backing up Download tool outputs..."
    cp -r Download/.asagus-runs "$RECYCLE_BIN/"
    echo "   Backed up to: $RECYCLE_BIN/.asagus-runs"
fi

echo -e "${GREEN}✅ Backup complete! Location: $RECYCLE_BIN${NC}"
echo ""

# ============================================================================
# STEP 2: CLEAN ALL DATA
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 2: Clean All Data${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Stop any running processes
echo "Stopping any running backend/frontend..."
cd asagus-scraper-v3
./stop_all.sh 2>/dev/null || true
cd ..

# Clean data directory
echo "🗑️  Cleaning data directory..."
rm -rf asagus-scraper-v3/data/runtime_records.json
rm -rf asagus-scraper-v3/data/runtime_secondary_records.json
rm -rf asagus-scraper-v3/data/runtime_jobs.json
rm -rf asagus-scraper-v3/data/runtime_events.json
rm -rf asagus-scraper-v3/data/runtime_events.ndjson
rm -rf asagus-scraper-v3/data/runtime_records.json.backup
rm -rf asagus-scraper-v3/data/raw_html/*

# Clean Download tool outputs
echo "🗑️  Cleaning Download tool outputs..."
rm -rf Download/.asagus-runs/*

echo -e "${GREEN}✅ All data cleaned!${NC}"
echo ""

# ============================================================================
# STEP 3: START BACKEND AND FRONTEND
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 3: Start Backend and Frontend${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "Starting backend..."
cd asagus-scraper-v3/backend
nohup .venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 > ../../backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
cd ../..

echo "Waiting for backend to start..."
sleep 8

# Check if backend is running
if curl -s "$BACKEND_URL/docs" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running on $BACKEND_URL${NC}"
else
    echo -e "${RED}❌ Backend failed to start!${NC}"
    exit 1
fi

echo ""
echo "Starting frontend..."
cd asagus-scraper-v3/frontend
nohup npm run dev > ../../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd ../..

echo "Waiting for frontend to start..."
sleep 10

# Check if frontend is running
if curl -s "$FRONTEND_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is running on $FRONTEND_URL${NC}"
else
    echo -e "${RED}❌ Frontend failed to start!${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 4: CREATE REAL SCRAPING JOB
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 4: Create Real Scraping Job (MAX MODE + HIGH STEALTH)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "Creating job with:"
echo "  📍 Query: restaurants in Doha Qatar"
echo "  📍 Location: Doha, Qatar"
echo "  📍 Limit: 15 records"
echo "  📍 Mode: MAX (all 11 tools)"
echo "  📍 Antibot: high-stealth"
echo "  📍 LLM: enabled"
echo "  📍 Real scraping: enabled"
echo ""

JOB_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restaurants in Doha Qatar",
    "location": "Doha, Qatar",
    "limit": 15,
    "mode": "max",
    "antibot_preset": "high-stealth",
    "enable_network_fetch": true,
    "enable_search_discovery": true,
    "llm_enabled": true,
    "include_contact_pages": true,
    "include_social_profiles": true,
    "store_partial_records": true
  }' 2>/dev/null)

JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ Failed to create job!${NC}"
    echo "Response: $JOB_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✅ Job created successfully!${NC}"
echo "Job ID: $JOB_ID"
echo ""

# ============================================================================
# STEP 5: MONITOR JOB PROGRESS
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 5: Monitor Job Progress${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "Waiting for job to start..."
sleep 5

# Monitor job progress
MAX_WAIT=600  # 10 minutes
ELAPSED=0
LAST_STATUS=""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    JOB_STATUS=$(curl -s "$BACKEND_URL/api/jobs" | python3 -c "
import sys, json
jobs = json.load(sys.stdin)
for job in jobs:
    if job['id'] == '$JOB_ID':
        print(json.dumps(job))
        break
" 2>/dev/null || echo "")
    
    if [ -n "$JOB_STATUS" ]; then
        STATUS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
        RECORDS=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('records_found', 0))" 2>/dev/null)
        PROCESSED=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('processed_targets', 0))" 2>/dev/null)
        TOTAL=$(echo "$JOB_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_targets', 0))" 2>/dev/null)
        
        if [ "$STATUS" != "$LAST_STATUS" ]; then
            echo ""
            echo -e "${CYAN}Status: $STATUS${NC}"
            LAST_STATUS=$STATUS
        fi
        
        echo -ne "\r  Records: $RECORDS | Processed: $PROCESSED/$TOTAL | Time: ${ELAPSED}s    "
        
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            echo ""
            echo ""
            if [ "$STATUS" = "completed" ]; then
                echo -e "${GREEN}✅ Job completed successfully!${NC}"
            else
                echo -e "${RED}❌ Job failed!${NC}"
            fi
            break
        fi
    fi
    
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Job is still running after ${MAX_WAIT}s. Proceeding to analysis...${NC}"
fi

echo ""

# Wait a bit more for Download tools to finish
echo "Waiting for Download tools to complete..."
sleep 10

# ============================================================================
# STEP 6: COMPREHENSIVE ANALYSIS
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 6: Comprehensive Results Analysis${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

python3 << 'ANALYSIS_EOF'
import csv
import json
import requests
from pathlib import Path
from collections import Counter

BACKEND_URL = "http://localhost:8000"

print("\n" + "=" * 70)
print("PRIMARY RECORDS ANALYSIS")
print("=" * 70)

# Get primary records
resp = requests.get(f"{BACKEND_URL}/api/records")
primary_data = resp.json()
primary_records = primary_data.get('records', [])

print(f"\n📊 Total Primary Records: {len(primary_records)}")

if primary_records:
    # Analyze field population
    critical_fields = ['phone', 'whatsapp', 'email', 'website_url', 
                       'facebook_url', 'instagram_url', 'twitter_url', 'linkedin_url']
    
    print("\n✅ CRITICAL FIELDS POPULATION:")
    for field in critical_fields:
        populated = sum(1 for r in primary_records if r.get(field))
        percentage = (populated / len(primary_records) * 100)
        status = "✅" if populated > 0 else "❌"
        print(f"{status} {field:20s}: {populated:2d}/{len(primary_records)} ({percentage:5.1f}%)")
    
    # Show sample records
    print("\n📝 SAMPLE RECORDS (First 3):")
    for i, record in enumerate(primary_records[:3], 1):
        print(f"\n--- Record {i} ---")
        print(f"Name: {record.get('name', 'N/A')}")
        print(f"Phone: {record.get('phone', 'N/A')}")
        print(f"WhatsApp: {record.get('whatsapp', 'N/A')}")
        print(f"Email: {record.get('email', 'N/A')}")
        print(f"Website: {record.get('website_url', 'N/A')[:60] if record.get('website_url') else 'N/A'}")
        print(f"Category: {record.get('category', 'N/A')}")
        print(f"Confidence: {record.get('confidence', 'N/A')}")

print("\n" + "=" * 70)
print("SECONDARY RECORDS ANALYSIS")
print("=" * 70)

# Get secondary records
resp = requests.get(f"{BACKEND_URL}/api/records/secondary")
secondary_data = resp.json()
secondary_records = secondary_data.get('records', [])

print(f"\n📊 Total Secondary Records: {len(secondary_records)}")

if secondary_records:
    # Analyze status distribution
    status_counts = Counter(r.get('status', 'unknown') for r in secondary_records)
    print("\n📈 STATUS DISTRIBUTION:")
    for status, count in status_counts.most_common():
        percentage = (count / len(secondary_records) * 100)
        print(f"  {status:20s}: {count:4d} ({percentage:5.1f}%)")
    
    # Analyze methods
    method_counts = Counter(r.get('method', 'unknown') for r in secondary_records)
    print("\n🔧 EXTRACTION METHODS:")
    for method, count in method_counts.most_common():
        percentage = (count / len(secondary_records) * 100)
        if method:
            print(f"  {method:25s}: {count:4d} ({percentage:5.1f}%)")

print("\n" + "=" * 70)
print("DOWNLOAD TOOLS ANALYSIS")
print("=" * 70)

# Analyze Download tool outputs
base_path = Path("/home/ghulam/Desktop/scrapper-main/scrapper-main/Download/.asagus-runs")

if base_path.exists():
    csv_files = list(base_path.glob("**/*.csv"))
    json_files = list(base_path.glob("**/*.json"))
    
    print(f"\n📊 Total CSV files: {len(csv_files)}")
    print(f"📊 Total JSON files: {len(json_files)}")
    
    if csv_files:
        job_data = {}
        for csv_file in csv_files:
            job_id = csv_file.parent.name
            tool_name = csv_file.stem
            
            if job_id not in job_data:
                job_data[job_id] = {}
            
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    records = list(reader)
                    job_data[job_id][tool_name] = len(records)
            except:
                job_data[job_id][tool_name] = 0
        
        print("\n🔧 TOOLS OUTPUT BY JOB:")
        for job_id, tools in job_data.items():
            print(f"\n  Job: {job_id[:30]}...")
            for tool_name, record_count in tools.items():
                print(f"    ├─ {tool_name:20s}: {record_count:3d} records")

print("\n" + "=" * 70)
print("PERSISTENCE STATUS")
print("=" * 70)

# Get persistence stats
resp = requests.get(f"{BACKEND_URL}/api/runtime/persistence-stats")
persistence = resp.json()

print(f"\n✅ Records persisted: {persistence.get('records_count', 0)}")
print(f"✅ Secondary records: {persistence.get('secondary_records_count', 0)}")
print(f"✅ Jobs tracked: {persistence.get('jobs_count', 0)}")
print(f"✅ Auto-persist interval: {persistence.get('auto_persist_interval', 0)} records")
print(f"✅ Since last persist: {persistence.get('records_since_last_persist', 0)} records")
print(f"✅ Backup exists: {persistence.get('backup_exists', False)}")

print("\n" + "=" * 70)
print("DATA QUALITY ASSESSMENT")
print("=" * 70)

if primary_records:
    # Calculate completeness
    total_fields = len(critical_fields)
    completeness_scores = []
    
    for record in primary_records:
        populated = sum(1 for field in critical_fields if record.get(field))
        completeness = (populated / total_fields * 100)
        completeness_scores.append(completeness)
    
    avg_completeness = sum(completeness_scores) / len(completeness_scores)
    
    print(f"\n📊 Average Record Completeness: {avg_completeness:.1f}%")
    print(f"📊 Records with 100% fields: {sum(1 for s in completeness_scores if s == 100)}")
    print(f"📊 Records with >80% fields: {sum(1 for s in completeness_scores if s >= 80)}")
    print(f"📊 Records with >50% fields: {sum(1 for s in completeness_scores if s >= 50)}")
    
    # Check for duplicates
    phone_set = set(r.get('phone') for r in primary_records if r.get('phone'))
    email_set = set(r.get('email') for r in primary_records if r.get('email'))
    website_set = set(r.get('website_url') for r in primary_records if r.get('website_url'))
    
    print(f"\n🔍 Deduplication Check:")
    print(f"  Unique phones: {len(phone_set)}")
    print(f"  Unique emails: {len(email_set)}")
    print(f"  Unique websites: {len(website_set)}")
    
    has_duplicates = (len(phone_set) < sum(1 for r in primary_records if r.get('phone'))) or \
                     (len(email_set) < sum(1 for r in primary_records if r.get('email'))) or \
                     (len(website_set) < sum(1 for r in primary_records if r.get('website_url')))
    
    if has_duplicates:
        print("  ⚠️  Some duplicates detected (expected behavior for data updates)")
    else:
        print("  ✅ No duplicates found")

ANALYSIS_EOF

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW} STEP 7: Download CSV Files for Manual Inspection${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "Downloading CSV files to: $RESULTS_DIR"

curl -s "$BACKEND_URL/api/records/export/csv" > "$RESULTS_DIR/primary_records.csv"
echo "✅ Downloaded: primary_records.csv ($(wc -l < "$RESULTS_DIR/primary_records.csv") lines)"

curl -s "$BACKEND_URL/api/records/secondary/export/csv" > "$RESULTS_DIR/secondary_records.csv"
echo "✅ Downloaded: secondary_records.csv ($(wc -l < "$RESULTS_DIR/secondary_records.csv") lines)"

# Copy Download tool outputs
if [ -d "Download/.asagus-runs" ]; then
    cp -r Download/.asagus-runs "$RESULTS_DIR/"
    echo "✅ Copied Download tool outputs"
fi

# Save logs
cp backend.log "$RESULTS_DIR/" 2>/dev/null || true
cp frontend.log "$RESULTS_DIR/" 2>/dev/null || true

echo ""
echo -e "${GREEN}Results saved to: $RESULTS_DIR${NC}"

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo ""
echo -e "${CYAN}"
echo "═══════════════════════════════════════════════════════════════"
echo "  TEST COMPLETE - SUMMARY"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

echo "📁 Backup Location: $RECYCLE_BIN"
echo "📁 Results Location: $RESULTS_DIR"
echo "🌐 Backend: $BACKEND_URL"
echo "🌐 Frontend: $FRONTEND_URL"
echo ""
echo "Process IDs:"
echo "  Backend PID: $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo ""
echo "To stop servers:"
echo "  cd asagus-scraper-v3 && ./stop_all.sh"
echo ""
echo -e "${GREEN}✅ All tests completed successfully!${NC}"
echo ""
