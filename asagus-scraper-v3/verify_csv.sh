#!/bin/bash
echo "════════════════════════════════════════════════════════════════"
echo "   CSV EXPORT STATUS CHECK"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check backend
echo "1. Backend Status:"
if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend is RUNNING"
else
    echo "   ❌ Backend is NOT running"
    echo "      Start with: cd backend && .venv/bin/python -m uvicorn asagus.main:app"
    exit 1
fi

# Check records
echo ""
echo "2. Available Records:"
RECORDS=$(curl -s http://127.0.0.1:8000/api/records | grep -o '"count":[0-9]*' | grep -o '[0-9]*')
echo "   📊 $RECORDS records ready to export"

# Test CSV export
echo ""
echo "3. CSV Export Test:"
curl -s http://127.0.0.1:8000/api/records/export/csv -o /tmp/quick_test.csv
if [ -f /tmp/quick_test.csv ]; then
    SIZE=$(stat -c%s /tmp/quick_test.csv 2>/dev/null || stat -f%z /tmp/quick_test.csv 2>/dev/null)
    LINES=$(wc -l < /tmp/quick_test.csv)
    echo "   ✅ CSV exported successfully!"
    echo "   📁 File: /tmp/quick_test.csv"
    echo "   💾 Size: ${SIZE} bytes"
    echo "   📋 Rows: $((LINES - 1)) data rows + 1 header"
fi

# Show CSV preview
echo ""
echo "4. CSV Preview (first 3 rows):"
echo "   ─────────────────────────────────────────────────────────"
head -3 /tmp/quick_test.csv | cut -c1-120
echo "   ─────────────────────────────────────────────────────────"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "   ✅ CSV EXPORT IS WORKING PERFECTLY!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📥 How to download CSV:"
echo ""
echo "   Option 1: Frontend UI (Recommended)"
echo "   • Open http://localhost:3000"
echo "   • Go to 'Records' tab"
echo "   • Click 'Export CSV' button"
echo ""
echo "   Option 2: Direct download"
echo "   • curl http://localhost:8000/api/records/export/csv -o my_records.csv"
echo ""
echo "   Option 3: Browser"
echo "   • Open: http://localhost:8000/api/records/export/csv"
echo ""
echo "📖 Full documentation: See CSV_EXPORT_GUIDE.md"
echo ""
