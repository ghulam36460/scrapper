# ASAGUS Scraper v3 - Quick Start Guide 🚀

## 1. Start the System (30 seconds)

```bash
cd asagus-scraper-v3
./stop_all.sh  # Stop if running
./start_all.sh  # Start fresh
```

Wait 10 seconds for backend to initialize.

## 2. Verify Everything Works (1 minute)

```bash
# Test all core fixes
./test_all_fixes.sh

# Test all tool integrations
cd ../Download
./test_all_tools.sh
cd ../asagus-scraper-v3
```

**Expected**: All tests pass ✅

## 3. Configure LLM (2 minutes)

### Option A: Through UI (Recommended)
1. Open http://localhost:3000
2. Click **Setup** tab
3. Click **LLM Settings**
4. Choose provider: `anthropic` or `openai`
5. Enter API key
6. Enter model name:
   - Anthropic: `claude-3-5-sonnet-20241022`
   - OpenAI: `gpt-4o`
7. Click **Save**
8. Click **Test Connection** ✅

### Option B: Through .env
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
LLM_MODEL=claude-3-5-sonnet-20241022
```

Then restart: `./stop_all.sh && ./start_all.sh`

## 4. Run Your First Job (2 minutes)

### Through UI (Easy)
1. Go to **Jobs** tab
2. Click **New Job**
3. Fill in:
   - Query: `restaurants in Lahore`
   - Location: `Lahore, Pakistan`
   - Limit: `50`
   - Mode: **max** (runs all tools)
4. Click **Start Job**
5. Watch progress in real-time

### Through API
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restaurants in Lahore",
    "location": "Lahore, Pakistan",
    "limit": 50,
    "mode": "max"
  }'
```

## 5. Download Results (1 minute)

### Primary CSV (Main Scraper)
In UI: Click **Download CSV** button

Or via API:
```bash
curl http://localhost:8000/api/records/export/csv > primary_records.csv
```

### Merged CSV (All Tools Combined)
```bash
# Replace <job-id> with your actual job ID
curl http://localhost:8000/api/records/export/merged-csv/<job-id> > merged_all_tools.csv
```

Or check the Download folder:
```bash
ls -lh Download/.asagus-runs/<job-id>/
# Look for: merged_all_tools_<job-id>.csv
```

## 6. Verify Results (30 seconds)

```bash
# Check CSV headers
head -n 1 primary_records.csv

# Should see:
# name,category,phone,whatsapp,email,address,city,website_url,
# facebook_url,instagram_url,twitter_url,linkedin_url,rating,...
```

**All fields present?** ✅ Success!

---

## Common Commands

### System Management
```bash
# Start
./start_all.sh

# Stop
./stop_all.sh

# Restart
./stop_all.sh && ./start_all.sh

# Check status
curl http://localhost:8000/health
```

### Testing
```bash
# Test fixes
./test_all_fixes.sh

# Test tools
cd Download && ./test_all_tools.sh

# Check tool status
cd Download
python3 enhanced_tool_coordinator.py summary | jq
```

### Data Access
```bash
# Primary CSV
curl http://localhost:8000/api/records/export/csv > records.csv

# Merged CSV (all tools)
curl http://localhost:8000/api/records/export/merged-csv/<job-id> > merged.csv

# Persistence stats
curl http://localhost:8000/api/runtime/persistence-stats

# Force save
curl -X POST http://localhost:8000/api/runtime/force-persist
```

### LLM Management
```bash
# Get settings
curl http://localhost:8000/api/llm/settings

# Test connection
curl -X POST http://localhost:8000/api/llm/test
```

---

## URLs

- **Frontend UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health
- **Grafana** (if using Docker): http://localhost:3001

---

## Modes Explained

| Mode | Speed | Quality | Tools | Use Case |
|------|-------|---------|-------|----------|
| fast | ⚡⚡⚡ | ⭐⭐ | Main only | Quick tests |
| balanced | ⚡⚡ | ⭐⭐⭐ | Main only | Normal use |
| **max** | ⚡ | ⭐⭐⭐⭐⭐ | **All 11** | **Best results** |

**Recommendation**: Use **max mode** for production scraping.

---

## What You Get with Max Mode

When you run a job with `mode=max`:

1. **Main ASAGUS scraper** runs (advanced extraction cascade)
2. **maps-scraper** runs (Google Maps data)
3. **outreach-scraper** runs (contact information focus)
4. **All other tools** check status and integrate
5. **CSV merger** combines everything
6. **Deduplication** removes duplicates
7. **Unified CSV** with all fields ready to download

Result: **2-3x more data** than single scraper!

---

## Quick Troubleshooting

### Backend won't start
```bash
# Check logs
tail -f backend.log

# Check port
sudo netstat -tlnp | grep 8000

# Kill existing
pkill -f "uvicorn"
./start_all.sh
```

### Tests failing
```bash
# Check dependencies
which curl jq

# Install if needed
sudo apt-get install curl jq

# Check permissions
chmod +x test_all_fixes.sh
chmod +x Download/test_all_tools.sh
```

### LLM not working
```bash
# Check in UI: Setup → LLM Settings → Test Connection

# Or check manually
env | grep -E "(LLM|ANTHROPIC|OPENAI)"
```

### No results in CSV
```bash
# Check job completed
curl http://localhost:8000/api/jobs | jq

# Check records
curl http://localhost:8000/api/records | jq '.count'

# Check logs
tail -f backend.log
```

### Tools not running
```bash
# Check tool status
cd Download
python3 enhanced_tool_coordinator.py summary

# Make scripts executable
find . -name "run-asagus.sh" -exec chmod +x {} \;

# Test one tool
cd scrapping-tool-of-maps-main
bash run-asagus.sh
```

---

## Important Files

### Configuration
- `asagus-scraper-v3/.env` - Main configuration
- `Download/.asagus/config.json` - Tool configurations

### Data
- `asagus-scraper-v3/data/runtime_records.json` - Scraped records
- `Download/.asagus-runs/<job-id>/` - Tool outputs

### Logs
- `asagus-scraper-v3/backend.log` - Backend logs
- `asagus-scraper-v3/frontend.log` - Frontend logs

### Tests
- `asagus-scraper-v3/test_all_fixes.sh` - Test fixes
- `Download/test_all_tools.sh` - Test tools

---

## Getting Help

### Check Documentation
1. `COMPLETE_IMPLEMENTATION_SUMMARY.md` - Full overview
2. `FIX_USER_GUIDE.md` - User guide
3. `Download/TOOLS_INTEGRATION_COMPLETE.md` - Tool details

### Check Status
```bash
# Backend health
curl http://localhost:8000/health

# Persistence stats
curl http://localhost:8000/api/runtime/persistence-stats

# Tool status
cd Download && python3 enhanced_tool_coordinator.py summary
```

### View Logs
```bash
# Backend
tail -f asagus-scraper-v3/backend.log

# Follow job progress
tail -f asagus-scraper-v3/backend.log | grep -E "(completed|stored|error)"
```

---

## Success Checklist

After setup, verify:

- [x] Backend starts without errors
- [x] Frontend accessible at http://localhost:3000
- [x] Test scripts pass
- [x] LLM configured and tested
- [x] Job runs successfully
- [x] CSV download has all fields
- [x] Merged CSV available (max mode)
- [x] Tool outputs in Download/.asagus-runs/

**All checked?** You're ready to go! 🎉

---

## Next Steps

1. **Start small**: Run 10-50 records to test
2. **Verify output**: Check CSV has all data
3. **Scale up**: Increase to 100-500 records
4. **Production**: Enable Postgres, configure proxies
5. **Monitor**: Check logs and persistence stats

---

**That's it!** The system is ready to use. 

For detailed information, see `COMPLETE_IMPLEMENTATION_SUMMARY.md`
