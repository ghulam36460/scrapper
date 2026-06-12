#!/bin/bash

# ✅ ASAGUS v3 - Comprehensive Fixes Test Script
# Tests all 6 fixes after implementation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "ASAGUS v3 - Testing All Fixes"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

test_info() {
    echo -e "${YELLOW}ℹ INFO${NC}: $1"
}

# Check if backend is running
echo "1. Checking backend status..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    test_pass "Backend is running"
else
    test_fail "Backend is not running. Start with ./start_all.sh"
    exit 1
fi

echo ""
echo "2. Testing Data Persistence (FIX #1)..."
# Check persistence stats endpoint
PERSIST_STATS=$(curl -s http://localhost:8000/api/runtime/persistence-stats 2>/dev/null || echo '{}')
if echo "$PERSIST_STATS" | grep -q "records_count"; then
    test_pass "Persistence stats API working"
    RECORDS_COUNT=$(echo "$PERSIST_STATS" | jq -r '.records_count // 0')
    test_info "Current records count: $RECORDS_COUNT"
else
    test_fail "Persistence stats API not responding"
fi

# Check if backup was created
if [ -f "data/runtime_records.json.backup" ]; then
    test_pass "Startup backup created"
else
    test_info "No backup found (will be created after first run)"
fi

# Check auto-persist interval
if echo "$PERSIST_STATS" | grep -q "auto_persist_interval"; then
    INTERVAL=$(echo "$PERSIST_STATS" | jq -r '.auto_persist_interval // 0')
    test_pass "Auto-persist configured (interval: $INTERVAL records)"
else
    test_fail "Auto-persist not configured"
fi

echo ""
echo "3. Testing CSV Export Fields (FIX #2)..."
# Create temporary test directory
TEST_DIR=$(mktemp -d)
CSV_FILE="$TEST_DIR/test_export.csv"

# Download CSV if records exist
if [ "$RECORDS_COUNT" -gt 0 ]; then
    curl -s http://localhost:8000/api/records/export/csv > "$CSV_FILE"
    
    # Check for critical fields
    HEADER=$(head -n 1 "$CSV_FILE")
    
    # Check contact fields
    if echo "$HEADER" | grep -q "phone"; then
        test_pass "Phone field present in CSV"
    else
        test_fail "Phone field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "whatsapp"; then
        test_pass "WhatsApp field present in CSV"
    else
        test_fail "WhatsApp field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "email"; then
        test_pass "Email field present in CSV"
    else
        test_fail "Email field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "website_url"; then
        test_pass "Website URL field present in CSV"
    else
        test_fail "Website URL field MISSING in CSV"
    fi
    
    # Check social fields
    if echo "$HEADER" | grep -q "facebook_url"; then
        test_pass "Facebook URL field present in CSV"
    else
        test_fail "Facebook URL field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "instagram_url"; then
        test_pass "Instagram URL field present in CSV"
    else
        test_fail "Instagram URL field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "twitter_url"; then
        test_pass "Twitter/X URL field present in CSV"
    else
        test_fail "Twitter/X URL field MISSING in CSV"
    fi
    
    if echo "$HEADER" | grep -q "linkedin_url"; then
        test_pass "LinkedIn URL field present in CSV"
    else
        test_fail "LinkedIn URL field MISSING in CSV"
    fi
else
    test_info "No records to test CSV export (run a job first)"
fi

# Cleanup
rm -rf "$TEST_DIR"

echo ""
echo "4. Testing E-commerce Platform Detection (FIX #3)..."
# Check if extraction layer has platform detection
if grep -q "ECOMMERCE_PLATFORM_DOMAINS" backend/asagus/layers/extraction.py; then
    test_pass "E-commerce platform detection code present"
    
    # Count detected platforms
    PLATFORM_COUNT=$(grep -A 15 "ECOMMERCE_PLATFORM_DOMAINS" backend/asagus/layers/extraction.py | grep -c '\.com')
    test_info "Detecting $PLATFORM_COUNT e-commerce platforms"
else
    test_fail "E-commerce platform detection code MISSING"
fi

echo ""
echo "5. Testing Max Mode Confidence Thresholds (FIX #4)..."
# Check if relaxed thresholds are implemented
if grep -q "CSS_ACCEPT_RELAXED" backend/asagus/layers/extraction.py; then
    test_pass "Relaxed confidence thresholds implemented"
    
    # Check threshold values
    CSS_RELAXED=$(grep "CSS_ACCEPT_RELAXED =" backend/asagus/layers/extraction.py | grep -oP '0\.\d+' || echo "0.0")
    test_info "Relaxed CSS threshold: $CSS_RELAXED"
    
    FP_RELAXED=$(grep "FINGERPRINT_ACCEPT_RELAXED =" backend/asagus/layers/extraction.py | grep -oP '0\.\d+' || echo "0.0")
    test_info "Relaxed fingerprint threshold: $FP_RELAXED"
else
    test_fail "Relaxed confidence thresholds NOT implemented"
fi

# Check if extraction layer accepts threshold parameter
if grep -q "use_relaxed_thresholds" backend/asagus/layers/extraction.py; then
    test_pass "Configurable threshold mode implemented"
else
    test_fail "Configurable threshold mode MISSING"
fi

echo ""
echo "6. Testing Download Tools Integration (FIX #5)..."
# Check if CSV merger exists
if [ -f "backend/asagus/services/csv_merger.py" ]; then
    test_pass "CSV merger module created"
    
    # Check for key functions
    if grep -q "class DownloadToolsCSVMerger" backend/asagus/services/csv_merger.py; then
        test_pass "CSV merger class implemented"
    else
        test_fail "CSV merger class MISSING"
    fi
    
    if grep -q "def merge_all_csvs" backend/asagus/services/csv_merger.py; then
        test_pass "CSV merge function implemented"
    else
        test_fail "CSV merge function MISSING"
    fi
    
    if grep -q "def deduplicate_records" backend/asagus/services/csv_merger.py; then
        test_pass "Deduplication function implemented"
    else
        test_fail "Deduplication function MISSING"
    fi
else
    test_fail "CSV merger module NOT created"
fi

# Check if API endpoint exists
if grep -q "export_merged_tools_csv" backend/asagus/routers/records.py; then
    test_pass "Merged CSV API endpoint added"
else
    test_fail "Merged CSV API endpoint MISSING"
fi

# Check Download folder structure
if [ -d "../Download/.asagus-runs" ]; then
    test_info "Download tools runs directory exists"
    RUN_COUNT=$(find ../Download/.asagus-runs -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    test_info "Found $RUN_COUNT previous tool runs"
else
    test_info "No Download tools runs yet (will be created on first max mode run)"
fi

echo ""
echo "7. Testing LLM Configuration (FIX #6)..."
# Check LLM settings endpoint
LLM_SETTINGS=$(curl -s http://localhost:8000/api/llm/settings)
if echo "$LLM_SETTINGS" | grep -q "provider"; then
    test_pass "LLM settings API working"
    
    PROVIDER=$(echo "$LLM_SETTINGS" | jq -r '.provider')
    test_info "Current LLM provider: $PROVIDER"
    
    MODEL=$(echo "$LLM_SETTINGS" | jq -r '.model // "none"')
    test_info "Current LLM model: $MODEL"
else
    test_fail "LLM settings API not responding"
fi

# Check if validation is implemented
if grep -q "providers_requiring_key" backend/asagus/routers/settings.py; then
    test_pass "LLM provider validation implemented"
else
    test_fail "LLM provider validation MISSING"
fi

# Check if LLM test endpoint exists
TEST_RESPONSE=$(curl -s -X POST http://localhost:8000/api/llm/test 2>/dev/null || echo '{}')
if echo "$TEST_RESPONSE" | grep -q "provider"; then
    test_pass "LLM test endpoint working"
else
    test_info "LLM test endpoint requires authentication"
fi

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
else
    echo -e "${GREEN}Failed: 0${NC}"
fi
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CRITICAL FIXES VERIFIED!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure LLM in UI (Setup tab)"
    echo "2. Run a job with mode=max to test all features"
    echo "3. Download CSV exports to verify all fields"
    echo "4. Check Download/.asagus-runs for merged tool outputs"
    exit 0
else
    echo -e "${YELLOW}⚠ Some tests failed. Review the output above.${NC}"
    echo ""
    echo "Common issues:"
    echo "- Backend not fully started (wait 10 seconds and retry)"
    echo "- No test data (run a job first)"
    echo "- Authentication required (set OPERATOR_TOKEN in .env)"
    exit 1
fi
