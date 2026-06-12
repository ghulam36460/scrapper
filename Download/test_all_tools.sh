#!/bin/bash
# Test All Download Tools Integration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Testing All Download Tools Integration"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Set test environment
export ASAGUS_JOB_ID="test-integration"
export ASAGUS_QUERY="test query"
export ASAGUS_LOCATION="test location"
export ASAGUS_LIMIT=5
export ASAGUS_MODE="max"
export ASAGUS_TOOL_REAL_RUN=0  # Dry run for testing
export ASAGUS_RUNS_ROOT="$SCRIPT_DIR/.asagus-runs"

echo "Test Environment:"
echo "  Job ID: $ASAGUS_JOB_ID"
echo "  Query: $ASAGUS_QUERY"
echo "  Location: $ASAGUS_LOCATION"
echo "  Mode: $ASAGUS_MODE"
echo "  Real Run: $ASAGUS_TOOL_REAL_RUN"
echo ""

# Test counters
TESTED=0
PASSED=0
FAILED=0

test_tool() {
    local tool_name=$1
    local tool_dir=$2
    
    ((TESTED++))
    echo -n "Testing $tool_name... "
    
    if [ ! -d "$tool_dir" ]; then
        echo -e "${RED}SKIP${NC} (directory not found)"
        return
    fi
    
    if [ ! -f "$tool_dir/run-asagus.sh" ]; then
        echo -e "${RED}SKIP${NC} (run-asagus.sh not found)"
        return
    fi
    
    if [ ! -f "$tool_dir/asagus_adapter.py" ]; then
        echo -e "${RED}SKIP${NC} (asagus_adapter.py not found)"
        return
    fi
    
    # Run the tool
    cd "$tool_dir"
    if OUTPUT=$(bash run-asagus.sh 2>&1); then
        # Check if JSON output
        if echo "$OUTPUT" | jq empty 2>/dev/null; then
            STATUS=$(echo "$OUTPUT" | jq -r '.status // "unknown"')
            echo -e "${GREEN}PASS${NC} (status: $STATUS)"
            ((PASSED++))
        else
            echo -e "${YELLOW}WARN${NC} (no JSON output)"
        fi
    else
        echo -e "${RED}FAIL${NC}"
        ((FAILED++))
    fi
    cd "$SCRIPT_DIR"
}

echo "Testing tools:"
echo ""

# Test each tool
test_tool "maps-scraper" "scrapping-tool-of-maps-main"
test_tool "outreach-scraper" "scrapping-for-outreach-tool-main"
test_tool "scrapling" "Scrapling-main"
test_tool "scrapegraph-ai" "Scrapegraph-ai-main"
test_tool "scrapy" "scrapy-master"
test_tool "outreach-system" "outreach-system-main"
test_tool "agent-reach" "Agent-Reach-main"
test_tool "firecrawl" "firecrawl-main"
test_tool "maxun" "maxun-develop"
test_tool "whatsapp-detector" "whatsapp-number-detector-main"
test_tool "outreach" "outreach-main"

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Tested: $TESTED"
echo -e "${GREEN}Passed: $PASSED${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED${NC}"
else
    echo -e "${GREEN}Failed: 0${NC}"
fi
echo ""

# Check output directory
if [ -d ".asagus-runs/$ASAGUS_JOB_ID" ]; then
    echo "Output files created:"
    ls -lh ".asagus-runs/$ASAGUS_JOB_ID/" | grep -E "\.(json|csv)$" || echo "  (none)"
    echo ""
fi

# Test unified adapter
echo "Testing unified adapter:"
if python3 -c "import sys; sys.path.insert(0, '.'); from unified_tool_adapter import UnifiedToolAdapter; print('OK')" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} unified_tool_adapter.py works"
else
    echo -e "${RED}✗${NC} unified_tool_adapter.py has issues"
fi

# Test coordinator
echo ""
echo "Testing enhanced coordinator:"
if [ -f "enhanced_tool_coordinator.py" ]; then
    if python3 enhanced_tool_coordinator.py summary > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} enhanced_tool_coordinator.py works"
        echo ""
        echo "Tool status summary:"
        python3 enhanced_tool_coordinator.py summary | jq -r '.tools | to_entries[] | "  \(.key): \(.value.ready)"' 2>/dev/null || echo "  (jq not available)"
    else
        echo -e "${YELLOW}⚠${NC} enhanced_tool_coordinator.py has warnings"
    fi
else
    echo -e "${RED}✗${NC} enhanced_tool_coordinator.py not found"
fi

echo ""
if [ $FAILED -eq 0 ] && [ $PASSED -gt 0 ]; then
    echo -e "${GREEN}✓ All tools integrated successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run a real job with mode=max in the UI"
    echo "2. Check Download/.asagus-runs/<job-id>/ for outputs"
    echo "3. Use CSV merger to combine all tool outputs"
    exit 0
else
    echo -e "${YELLOW}⚠ Some tools need attention${NC}"
    echo ""
    echo "Check:"
    echo "- Tool adapters created (asagus_adapter.py)"
    echo "- Run scripts updated (run-asagus.sh)"
    echo "- Dependencies installed"
    exit 1
fi
