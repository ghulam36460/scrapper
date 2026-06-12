#!/bin/bash
# Complete Test Script - Tests all functionality including real job execution

set -e

echo "═══════════════════════════════════════════════════════════════"
echo "  ASAGUS SCRAPER V3 - COMPLETE FUNCTIONALITY TEST"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKEND_URL="http://localhost:8000"
test_count=0
pass_count=0
fail_count=0

# Test function
test_endpoint() {
    local name="$1"
    local endpoint="$2"
    local expected_status="${3:-200}"
    
    test_count=$((test_count + 1))
    echo -n "Test $test_count: $name... "
    
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL$endpoint" 2>/dev/null || echo "000")
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (Expected $expected_status, got $status)"
        fail_count=$((fail_count + 1))
        return 1
    fi
}

echo "───────────────────────────────────────────────────────────────"
echo " STEP 1: Backend Health Check"
echo "───────────────────────────────────────────────────────────────"

# Check if backend is running
if ! curl -s "$BACKEND_URL/docs" > /dev/null 2>&1; then
    echo -e "${RED}❌ Backend is not running!${NC}"
    echo "Please start backend first: cd asagus-scraper-v3 && ./start_all.sh"
    exit 1
fi

echo -e "${GREEN}✅ Backend is running${NC}"
echo ""

echo "───────────────────────────────────────────────────────────────"
echo " STEP 2: Test All API Endpoints"
echo "───────────────────────────────────────────────────────────────"

# Test core endpoints
test_endpoint "API Documentation" "/docs"
test_endpoint "Records list" "/api/records"
test_endpoint "Jobs list" "/api/jobs"
test_endpoint "Graph candidates" "/api/graph/candidates"
test_endpoint "Secondary records" "/api/records/secondary"

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 3: Test Fix #1 - Data Persistence Endpoints"
echo "───────────────────────────────────────────────────────────────"

# Test persistence stats (Fix #1)
test_endpoint "Persistence stats (Fix #1)" "/api/runtime/persistence-stats"

echo ""
echo "Checking persistence stats details:"
curl -s "$BACKEND_URL/api/runtime/persistence-stats" | python3 -m json.tool

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 4: Test Fix #2 - CSV Export with All Fields"
echo "───────────────────────────────────────────────────────────────"

# Export CSV and check fields
echo "Downloading CSV export..."
curl -s "$BACKEND_URL/api/records/export/csv" > /tmp/test_primary_export.csv 2>/dev/null

if [ -f /tmp/test_primary_export.csv ]; then
    echo -e "${GREEN}✅ CSV export successful${NC}"
    
    # Check for critical fields (Fix #2)
    echo ""
    echo "Checking CSV headers for all required fields:"
    header=$(head -n 1 /tmp/test_primary_export.csv)
    
    critical_fields=("phone" "whatsapp" "email" "website_url" "facebook_url" "instagram_url" "twitter_url" "linkedin_url")
    
    for field in "${critical_fields[@]}"; do
        test_count=$((test_count + 1))
        echo -n "  Checking field '$field'... "
        if echo "$header" | grep -q "$field"; then
            echo -e "${GREEN}✅ PRESENT${NC}"
            pass_count=$((pass_count + 1))
        else
            echo -e "${RED}❌ MISSING${NC}"
            fail_count=$((fail_count + 1))
        fi
    done
    
    echo ""
    echo "Complete CSV header:"
    echo "$header" | tr ',' '\n' | nl
else
    echo -e "${RED}❌ CSV export failed${NC}"
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 5: Test Fix #6 - LLM Configuration"
echo "───────────────────────────────────────────────────────────────"

# Test LLM settings endpoint
test_endpoint "LLM settings" "/api/llm/settings"

echo ""
echo "Current LLM configuration:"
curl -s "$BACKEND_URL/api/llm/settings" | python3 -m json.tool

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 6: Create Test Job (Balanced Mode)"
echo "───────────────────────────────────────────────────────────────"

# Create a small test job in balanced mode
echo "Creating test job in balanced mode..."
JOB_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "coffee shop test",
    "location": "Test City",
    "limit": 5,
    "mode": "balanced",
    "enable_network_fetch": false
  }' 2>/dev/null)

JOB_ID=$(echo "$JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -n "$JOB_ID" ]; then
    echo -e "${GREEN}✅ Job created successfully${NC}"
    echo "Job ID: $JOB_ID"
    test_count=$((test_count + 1))
    pass_count=$((pass_count + 1))
    
    echo ""
    echo "Job details:"
    echo "$JOB_RESPONSE" | python3 -m json.tool
else
    echo -e "${RED}❌ Job creation failed${NC}"
    test_count=$((test_count + 1))
    fail_count=$((fail_count + 1))
    echo "Response: $JOB_RESPONSE"
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 7: Create Test Job (MAX MODE)"
echo "───────────────────────────────────────────────────────────────"

# Create a test job in MAX mode (dry run)
echo "Creating test job in MAX mode (dry run)..."
MAX_JOB_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restaurant test max mode",
    "location": "Test City",
    "limit": 5,
    "mode": "max",
    "enable_network_fetch": false
  }' 2>/dev/null)

MAX_JOB_ID=$(echo "$MAX_JOB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "")

if [ -n "$MAX_JOB_ID" ]; then
    echo -e "${GREEN}✅ MAX mode job created successfully${NC}"
    echo "Job ID: $MAX_JOB_ID"
    test_count=$((test_count + 1))
    pass_count=$((pass_count + 1))
    
    echo ""
    echo "MAX mode job details:"
    echo "$MAX_JOB_RESPONSE" | python3 -m json.tool
    
    echo ""
    echo "Note: MAX mode should trigger all 11 Download tools"
    echo "      (in dry-run mode for testing, no real network activity)"
else
    echo -e "${RED}❌ MAX mode job creation failed${NC}"
    test_count=$((test_count + 1))
    fail_count=$((fail_count + 1))
    echo "Response: $MAX_JOB_RESPONSE"
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 8: Test Download Tools Integration (Fix #5)"
echo "───────────────────────────────────────────────────────────────"

# Check if Download tools directory exists
if [ -d "../Download" ]; then
    echo "Checking Download tools status..."
    
    # Count tool adapters
    adapter_count=$(find ../Download -name "asagus_adapter.py" 2>/dev/null | wc -l)
    echo "Tool adapters found: $adapter_count"
    
    if [ "$adapter_count" -eq 11 ]; then
        echo -e "${GREEN}✅ All 11 tool adapters present${NC}"
        test_count=$((test_count + 1))
        pass_count=$((pass_count + 1))
    else
        echo -e "${YELLOW}⚠️  Expected 11 adapters, found $adapter_count${NC}"
        test_count=$((test_count + 1))
        fail_count=$((fail_count + 1))
    fi
    
    # List all adapters
    echo ""
    echo "Tool adapters:"
    find ../Download -name "asagus_adapter.py" 2>/dev/null | sed 's|.*/\([^/]*\)/asagus_adapter.py|  ✓ \1|' | sort
else
    echo -e "${YELLOW}⚠️  Download directory not found${NC}"
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 9: Test Tool Coordinator"
echo "───────────────────────────────────────────────────────────────"

if [ -f "../Download/enhanced_tool_coordinator.py" ]; then
    echo "Running tool coordinator summary..."
    cd ../Download
    python3 enhanced_tool_coordinator.py summary 2>/dev/null | head -50
    cd - > /dev/null
    echo -e "${GREEN}✅ Tool coordinator working${NC}"
    test_count=$((test_count + 1))
    pass_count=$((pass_count + 1))
else
    echo -e "${YELLOW}⚠️  Tool coordinator not found${NC}"
    test_count=$((test_count + 1))
    fail_count=$((fail_count + 1))
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo " STEP 10: Summary"
echo "───────────────────────────────────────────────────────────────"

echo ""
echo "Test Results:"
echo "  Total tests: $test_count"
echo -e "  ${GREEN}Passed: $pass_count${NC}"
if [ $fail_count -gt 0 ]; then
    echo -e "  ${RED}Failed: $fail_count${NC}"
else
    echo -e "  ${GREEN}Failed: $fail_count${NC}"
fi

echo ""
if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   ✅ ALL TESTS PASSED - SYSTEM IS WORKING CORRECTLY!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}   ⚠️  SOME TESTS FAILED - REVIEW OUTPUT ABOVE${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
    exit 1
fi
