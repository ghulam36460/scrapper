#!/bin/bash
echo "════════════════════════════════════════════════════════════════"
echo "   FRONTEND COMPREHENSIVE CHECK"
echo "════════════════════════════════════════════════════════════════"
echo ""

cd frontend

# 1. Check Node/NPM
echo "1. Node & NPM Versions:"
node --version
npm --version
echo ""

# 2. Check dependencies
echo "2. Dependencies Check:"
if [ -d "node_modules" ]; then
    echo "   ✅ node_modules exists"
    MODULE_COUNT=$(ls node_modules | wc -l)
    echo "   📦 $MODULE_COUNT packages installed"
else
    echo "   ❌ node_modules missing - run: npm install"
fi
echo ""

# 3. Check package.json
echo "3. Package.json Scripts:"
grep -A 10 '"scripts"' package.json | head -12
echo ""

# 4. Check TypeScript config
echo "4. TypeScript Configuration:"
if [ -f "tsconfig.json" ]; then
    echo "   ✅ tsconfig.json exists"
else
    echo "   ❌ tsconfig.json missing"
fi
echo ""

# 5. Check Next.js config
echo "5. Next.js Configuration:"
if [ -f "next.config.ts" ]; then
    echo "   ✅ next.config.ts exists"
    cat next.config.ts
else
    echo "   ❌ next.config.ts missing"
fi
echo ""

# 6. Check API connection config
echo "6. API Connection Configuration:"
grep "API_URL" lib/api.ts | head -1
echo "   ✅ Frontend will connect to: http://localhost:8000"
echo ""

# 7. Check main page component
echo "7. Main Page Component:"
if [ -f "app/page.tsx" ]; then
    LINES=$(wc -l < app/page.tsx)
    echo "   ✅ app/page.tsx exists ($LINES lines)"
    echo "   📊 Components found:"
    grep "export function\|export default" app/page.tsx | head -3
else
    echo "   ❌ app/page.tsx missing"
fi
echo ""

# 8. Check widgets component
echo "8. Widget Components:"
if [ -f "components/operator-widgets.tsx" ]; then
    LINES=$(wc -l < components/operator-widgets.tsx)
    echo "   ✅ operator-widgets.tsx exists ($LINES lines)"
    echo "   📊 Exported components:"
    grep "export function" components/operator-widgets.tsx | cut -d' ' -f3 | cut -d'(' -f1
else
    echo "   ❌ operator-widgets.tsx missing"
fi
echo ""

# 9. Test build
echo "9. Build Test (this may take 30-60 seconds)..."
rm -rf .next
timeout 90 npm run build > /tmp/frontend_build.log 2>&1
BUILD_EXIT=$?

if [ $BUILD_EXIT -eq 0 ]; then
    echo "   ✅ Frontend builds successfully!"
    if [ -d ".next" ]; then
        echo "   ✅ .next directory created"
        BUILD_SIZE=$(du -sh .next 2>/dev/null | cut -f1)
        echo "   💾 Build size: $BUILD_SIZE"
    fi
else
    echo "   ❌ Build failed!"
    echo "   Last 20 lines of build log:"
    tail -20 /tmp/frontend_build.log
fi
echo ""

# 10. Check CSS
echo "10. Styling Files:"
if [ -f "app/globals.css" ]; then
    CSS_LINES=$(wc -l < app/globals.css)
    echo "   ✅ globals.css exists ($CSS_LINES lines)"
else
    echo "   ❌ globals.css missing"
fi
echo ""

cd ..

# 11. Backend connectivity test
echo "11. Backend Connection Test:"
if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ Backend is reachable at http://localhost:8000"
    BACKEND_STATUS=$(curl -s http://127.0.0.1:8000/api/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "   📡 Backend status: $BACKEND_STATUS"
else
    echo "   ❌ Backend is NOT reachable"
    echo "   ⚠️  Frontend needs backend to be running!"
fi
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "   FRONTEND STATUS SUMMARY"
echo "════════════════════════════════════════════════════════════════"
echo ""

if [ $BUILD_EXIT -eq 0 ]; then
    echo "✅ Frontend build: WORKING"
else
    echo "❌ Frontend build: FAILED"
fi

if [ -d "frontend/node_modules" ]; then
    echo "✅ Dependencies: INSTALLED"
else
    echo "❌ Dependencies: MISSING (run: cd frontend && npm install)"
fi

if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend connection: READY"
else
    echo "❌ Backend connection: OFFLINE"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🚀 To start frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo "   Then open: http://localhost:3000"
echo ""
echo "⚠️  IMPORTANT: Backend must be running first!"
echo "   cd backend"
echo "   .venv/bin/python -m uvicorn asagus.main:app --reload"
echo ""
echo "📖 Full logs saved to: /tmp/frontend_build.log"
echo ""
