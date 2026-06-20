# How to Start Backend and Frontend

## Quick Start (Recommended)

### Start Both Services
```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main
./START_SERVICES.sh
```

This will:
- Stop any running services
- Start backend on http://localhost:8000
- Start frontend on http://localhost:3000
- Show you the PIDs and log locations

### Stop Both Services
```bash
./STOP_SERVICES.sh
```

---

## Manual Start (Alternative)

### 1. Start Backend

```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload
```

**Backend URLs:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

### 2. Start Frontend (in new terminal)

```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/frontend
npm run dev
```

**Frontend URL:**
- App: http://localhost:3000

---

## Background Start (Services run in background)

### Start Backend in Background
```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/backend
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8000 --reload > backend.log 2>&1 &
echo "Backend PID: $!"
```

### Start Frontend in Background
```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main/asagus-scraper-v3/frontend
npm run dev > frontend.log 2>&1 &
echo "Frontend PID: $!"
```

### View Logs
```bash
# Backend logs
tail -f asagus-scraper-v3/backend/backend.log

# Frontend logs
tail -f asagus-scraper-v3/frontend/frontend.log
```

### Stop Background Services
```bash
# Stop backend
pkill -f "uvicorn asagus.main:app"

# Stop frontend
pkill -f "npm run dev"
pkill -f "vite"

# OR use the stop script
./STOP_SERVICES.sh
```

---

## Verify Services Are Running

### Check Backend
```bash
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok"}`

### Check Frontend
```bash
curl -I http://localhost:3000
```
Expected: HTTP 200 OK

### Check Processes
```bash
# Check backend process
ps aux | grep "uvicorn asagus.main:app" | grep -v grep

# Check frontend process
ps aux | grep "vite" | grep -v grep
```

---

## Troubleshooting

### Port 8000 Already in Use (Backend)
```bash
# Find what's using port 8000
lsof -i :8000

# Kill it
kill -9 $(lsof -t -i :8000)

# OR use different port
.venv/bin/python -m uvicorn asagus.main:app --host 127.0.0.1 --port 8001 --reload
```

### Port 3000 Already in Use (Frontend)
```bash
# Find what's using port 3000
lsof -i :3000

# Kill it
kill -9 $(lsof -t -i :3000)
```

### Backend Won't Start - Missing Dependencies
```bash
cd asagus-scraper-v3/backend
.venv/bin/pip install -r requirements.txt
```

### Frontend Won't Start - Missing Node Modules
```bash
cd asagus-scraper-v3/frontend
npm install
```

### Cannot Find Python venv
```bash
cd asagus-scraper-v3/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Quick Access Commands

### Start Everything
```bash
./START_SERVICES.sh
```

### Stop Everything
```bash
./STOP_SERVICES.sh
```

### Check Status
```bash
curl http://localhost:8000/api/health && echo "Backend: OK" || echo "Backend: NOT RUNNING"
curl -s http://localhost:3000 > /dev/null && echo "Frontend: OK" || echo "Frontend: NOT RUNNING"
```

### View Logs
```bash
# Backend
tail -f asagus-scraper-v3/backend/backend.log

# Frontend
tail -f asagus-scraper-v3/frontend/frontend.log
```

---

## After Starting Services

### Test Backend
```bash
# Check health
curl http://localhost:8000/api/health

# List jobs
curl http://localhost:8000/api/jobs

# List records
curl http://localhost:8000/api/records
```

### Open Frontend
Open your browser to: http://localhost:3000

### API Documentation
Open your browser to: http://localhost:8000/docs

---

## Scripts Available

| Script | Purpose |
|--------|---------|
| `START_SERVICES.sh` | Start backend + frontend |
| `STOP_SERVICES.sh` | Stop all services |
| `VERIFY_INTELLIGENT_BEHAVIOR.sh` | Full test with auto-start |
| `CLEAN_AND_TEST_COMPLETE.sh` | Clean data + full test |

---

## Summary

**Easiest way:**
```bash
cd /home/ghulam/Desktop/scrapper-main/scrapper-main
./START_SERVICES.sh
```

Then open http://localhost:3000 in your browser! ✅
