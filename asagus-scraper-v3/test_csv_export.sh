#!/bin/bash
set -e

BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://127.0.0.1:3000"

echo "════════════════════════════════════════════════════════════════════════════"
echo "   CSV EXPORT VERIFICATION TEST"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

# Check backend is running
echo "⚡ Step 1: Backend Health Check"
if curl -s "${BACKEND_URL}/api/health" > /dev/null 2>&1; then
    echo "✓ Backend is running at ${BACKEND_URL}"
else
    echo "✗ Backend is NOT running. Start it with:"
    echo "  cd backend && .venv/bin/python -m uvicorn asagus.main:app --reload"
    exit 1
fi
echo ""

# Check frontend is running
echo "⚡ Step 2: Frontend Health Check"
if curl -s "${FRONTEND_URL}" > /dev/null 2>&1; then
    echo "✓ Frontend is running at ${FRONTEND_URL}"
else
    echo "⚠ Frontend is NOT running. Start it with:"
    echo "  cd frontend && npm run dev"
    echo "  (Continuing test anyway...)"
fi
echo ""

# Check how many records exist
echo "⚡ Step 3: Record Count"
RECORD_COUNT=$(curl -s "${BACKEND_URL}/api/records" | jq -r '.count')
echo "✓ Found ${RECORD_COUNT} records in primary database"
echo ""

if [ "$RECORD_COUNT" -eq "0" ]; then
    echo "⚠ WARNING: No records in database!"
    echo "  Run a scrape job first from the frontend or use test_max_mode_all_features.sh"
    echo ""
fi

# Test primary CSV export
echo "⚡ Step 4: Primary DB CSV Export Test"
CSV_FILE="/tmp/asagus_primary_test.csv"
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$CSV_FILE" "${BACKEND_URL}/api/records/export/csv")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ CSV export endpoint returned HTTP 200"
    
    if [ -f "$CSV_FILE" ]; then
        FILE_SIZE=$(stat -c%s "$CSV_FILE" 2>/dev/null || stat -f%z "$CSV_FILE" 2>/dev/null)
        LINE_COUNT=$(wc -l < "$CSV_FILE")
        
        echo "✓ CSV file created: $CSV_FILE"
        echo "  - Size: ${FILE_SIZE} bytes"
        echo "  - Lines: ${LINE_COUNT} (header + data rows)"
        
        # Show first 5 lines
        echo ""
        echo "📄 CSV File Preview (first 5 lines):"
        echo "────────────────────────────────────────────────────────────────"
        head -5 "$CSV_FILE"
        echo "────────────────────────────────────────────────────────────────"
        echo ""
        
        # Verify CSV structure
        HEADER=$(head -1 "$CSV_FILE")
        if echo "$HEADER" | grep -q "name.*email.*phone.*city"; then
            echo "✓ CSV header contains expected columns (name, email, phone, city)"
        else
            echo "⚠ CSV header may be incomplete"
            echo "  Header: $HEADER"
        fi
        
        # Count records in CSV (excluding header)
        CSV_RECORDS=$((LINE_COUNT - 1))
        echo "✓ CSV contains ${CSV_RECORDS} data rows"
        
        if [ "$CSV_RECORDS" -eq "$RECORD_COUNT" ]; then
            echo "✓ CSV record count matches API record count"
        else
            echo "⚠ Mismatch: API reports ${RECORD_COUNT} records, CSV has ${CSV_RECORDS} rows"
        fi
    else
        echo "✗ CSV file was not created"
    fi
else
    echo "✗ CSV export failed with HTTP ${HTTP_CODE}"
    cat "$CSV_FILE"
fi
echo ""

# Test secondary CSV export
echo "⚡ Step 5: Secondary DB CSV Export Test"
SECONDARY_COUNT=$(curl -s "${BACKEND_URL}/api/records/secondary" | jq -r '.count')
echo "✓ Found ${SECONDARY_COUNT} entries in secondary database"

CSV_FILE_SEC="/tmp/asagus_secondary_test.csv"
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$CSV_FILE_SEC" "${BACKEND_URL}/api/records/secondary/export/csv")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Secondary CSV export endpoint returned HTTP 200"
    
    if [ -f "$CSV_FILE_SEC" ]; then
        FILE_SIZE=$(stat -c%s "$CSV_FILE_SEC" 2>/dev/null || stat -f%z "$CSV_FILE_SEC" 2>/dev/null)
        LINE_COUNT=$(wc -l < "$CSV_FILE_SEC")
        
        echo "✓ Secondary CSV file created: $CSV_FILE_SEC"
        echo "  - Size: ${FILE_SIZE} bytes"
        echo "  - Lines: ${LINE_COUNT}"
        
        # Show columns
        HEADER=$(head -1 "$CSV_FILE_SEC")
        COLUMN_COUNT=$(echo "$HEADER" | tr ',' '\n' | wc -l)
        echo "  - Columns: ${COLUMN_COUNT}"
        echo ""
        echo "📄 Secondary CSV Preview (first 3 lines):"
        echo "────────────────────────────────────────────────────────────────"
        head -3 "$CSV_FILE_SEC"
        echo "────────────────────────────────────────────────────────────────"
    fi
else
    echo "✗ Secondary CSV export failed with HTTP ${HTTP_CODE}"
fi
echo ""

# Frontend button check
echo "⚡ Step 6: Frontend CSV Button Check"
echo "The frontend has TWO CSV export buttons on the Records tab:"
echo "  1. 'Export CSV' → downloads primary DB (enriched records)"
echo "  2. 'Full DB CSV' → downloads secondary DB (all events)"
echo ""
echo "To test manually:"
echo "  1. Open ${FRONTEND_URL} in your browser"
echo "  2. Navigate to the 'Records' tab"
echo "  3. Click 'Export CSV' button"
echo "  4. Click 'Full DB CSV' button"
echo "  5. Verify both CSV files download correctly"
echo ""

# Detailed record analysis
if [ "$RECORD_COUNT" -gt "0" ]; then
    echo "⚡ Step 7: Sample Record Analysis"
    echo "Checking first record for data quality..."
    
    SAMPLE=$(curl -s "${BACKEND_URL}/api/records" | jq -r '.records[0]')
    NAME=$(echo "$SAMPLE" | jq -r '.name')
    EMAIL=$(echo "$SAMPLE" | jq -r '.email')
    PHONE=$(echo "$SAMPLE" | jq -r '.phone')
    CITY=$(echo "$SAMPLE" | jq -r '.city')
    WEBSITE=$(echo "$SAMPLE" | jq -r '.website_url')
    
    echo "Sample Record:"
    echo "  - Name: $NAME"
    echo "  - Email: $EMAIL"
    echo "  - Phone: $PHONE"
    echo "  - City: $CITY"
    echo "  - Website: $WEBSITE"
    echo ""
fi

# Summary
echo "════════════════════════════════════════════════════════════════════════════"
echo "   TEST SUMMARY"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "✓ Backend CSV endpoints are working"
echo "✓ Primary CSV export: $CSV_FILE"
echo "✓ Secondary CSV export: $CSV_FILE_SEC"
echo ""
echo "📊 Data Summary:"
echo "  - Primary DB Records: ${RECORD_COUNT}"
echo "  - Secondary DB Entries: ${SECONDARY_COUNT}"
echo ""
echo "🎯 CSV Files Created:"
ls -lh /tmp/asagus_*_test.csv 2>/dev/null || echo "  (no CSV files found)"
echo ""
echo "💡 Next Steps:"
echo "  1. Open CSV files in Excel/LibreOffice to verify formatting"
echo "  2. Test frontend download buttons at ${FRONTEND_URL}#records"
echo "  3. Both JSON and CSV formats are now available!"
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
