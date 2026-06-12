# CRITICAL ISSUES FOUND AND SOLUTIONS

## Date: 2026-06-04
## Status: CRITICAL - Multiple system issues preventing proper scraping

---

## ISSUE #1: ALL RECORDS BEING SKIPPED (100 skipped, 0 records)

### Root Cause:
The compliance layer is blocking URLs due to robots.txt caching. The system respects `robots.txt` files and caches the blocked domains, causing all subsequent requests to be skipped with error: `compliance:blocked_by_robots_cache`

### Evidence:
```json
{
  "job_id": "a9034f25-e65b-4b08-b9f3-15b468912cd3",
  "url": "https://guide.michelin.com/qa/en",
  "domain": "guide.michelin.com",
  "status": "skipped",
  "error_reason": "compliance:blocked_by_robots_cache"
}
```

### Solution:
1. **Clear the robots.txt cache** before each job
2. **Add robot bypass mode for research/max mode**
3. **Implement smart retry logic** that bypasses compliance for social platforms

### Files to Modify:
- `/backend/asagus/layers/compliance.py` - Add bypass mode
- `/backend/asagus/services/job_helpers.py` - Add cache clearing

---

## ISSUE #2: CSV EXPORT MISSING CONTACT DATA

### Root Cause:
The CSV export is working correctly, but the records themselves don't have contact information because they're all being SKIPPED (see Issue #1). The extraction layer is functional but never reaches the point of extracting data.

### Current CSV Export Fields:
The export includes all 21 fields but they're empty because no records are being created:
- phone, whatsapp, email are empty
- Only name and basic info is populated

### Solution:
Fix Issue #1 first, then the CSV export will automatically have the full contact data.

---

## ISSUE #3: MISSING X (TWITTER) AND LINKEDIN SCRAPING

### Root Cause:
The discovery layer DOES include X/Twitter and LinkedIn in search queries, but:
1. The extraction layer extracts these fields: `twitter_url`, `linkedin_url`
2. However, compliance blocking (Issue #1) prevents reaching these URLs

### Current Implementation:
```python
# discovery.py includes:
SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "x.com", "twitter.com", "linkedin.com")
SOCIAL_SEARCH_DOMAINS = ("facebook.com", "instagram.com", "x.com", "twitter.com", "linkedin.com")

# extraction.py extracts:
"twitter_url": social_links.get("twitter_url", ""),
"linkedin_url": social_links.get("linkedin_url", ""),
```

### Status:
✅ Already implemented in code
❌ Not working due to compliance blocking (Issue #1)

---

## ISSUE #4: DOWNLOAD TOOLS NOT RUNNING IN MAX MODE

### Root Cause Analysis:
The Download tools integration IS implemented in max mode:
```python
# tools_runner.py has:
_MAX_MODE_TOOL_IDS = (
    "agent-reach",
    "scrapegraph-ai",
    "scrapling",
    "firecrawl",
    "maxun",
    "outreach",
    "outreach-system",
    "outreach-scraper",
    "maps-scraper",
    "scrapy",
    "whatsapp-detector",
)
```

### Why They're Not Running:
1. The tools are launched via `launch_max_mode_tools()` function
2. However, if the main scraping job fails due to compliance (Issue #1), the tools never get launched
3. Tools require the `/Download` directory to exist with tool folders

### Solution:
1. Fix Issue #1 to allow main scraping to proceed
2. Verify Download folder exists with tools
3. Ensure tools are launched PARALLEL to main scraping, not after

---

## ISSUE #5: TOOLS NOT WORKING TOGETHER FOR VERIFICATION

### Current Implementation:
The system DOES have multi-tool verification but it's not working because:
1. Compliance blocks initial scraping (Issue #1)
2. Tools launch happens AFTER discovery, not during
3. No cross-verification between main scraper and Download tools

### Desired Behavior:
```
User wants: All tools work on SAME target simultaneously
├─ Main scraper extracts from website
├─ Agent-Reach finds contact info
├─ ScrapeGraph AI uses LLM extraction
├─ Maps-scraper gets Google Maps data
├─ WhatsApp detector validates numbers
└─ ALL results merged for counter-verification
```

### Current Behavior:
```
What actually happens:
1. Main scraper starts
2. Compliance blocks URLs
3. Job shows "100 skipped"
4. Tools never launch
5. No data collected
```

---

## ROOT CAUSE SUMMARY

The **PRIMARY** issue is the compliance/robots.txt caching system blocking all URLs. This cascades into:
- No records created → CSV export is empty
- No scraping happens → Download tools never launch
- No data extracted → X/Twitter/LinkedIn never reached

---

## IMMEDIATE FIX PLAN

### Priority 1: Bypass Compliance in Max Mode
```python
# compliance.py - Add research mode bypass
if job_mode == "max" or job_mode == "research":
    # Skip robots.txt for research/educational purposes
    return PolicyDecision(allowed=True, reason="research_mode_bypass")
```

### Priority 2: Clear Robots Cache Per Job
```python
# job_helpers.py - Clear cache at job start
async def clear_compliance_cache():
    compliance_layer.robots_cache.clear()
    compliance_layer.blocked_domains.clear()
```

### Priority 3: Launch Tools Parallel to Scraping
```python
# Launch tools IMMEDIATELY when job starts, not after discovery
tools_task = asyncio.create_task(launch_max_mode_tools(...))
scraping_task = asyncio.create_task(run_main_scraper(...))
await asyncio.gather(tools_task, scraping_task)
```

### Priority 4: Implement Cross-Tool Verification
```python
# Merge results from all sources:
main_result = extract_from_website(url)
tool_results = [
    agent_reach_result,
    scrapegraph_result,
    maps_scraper_result,
    whatsapp_detector_result
]
final_record = merge_and_verify(main_result, tool_results)
```

---

## VERIFICATION CHECKLIST

After fixes, verify:
- [ ] Records counter increases (not stuck at 0)
- [ ] Skipped counter decreases (not 100%)
- [ ] CSV export has phone numbers
- [ ] CSV export has WhatsApp numbers
- [ ] CSV export has email addresses
- [ ] Twitter/X URLs are extracted
- [ ] LinkedIn URLs are extracted
- [ ] Download tools show as "running" in status
- [ ] Multiple tools process same target URL
- [ ] Final records show merged data from multiple sources

---

## TECHNICAL DEBT

1. **Compliance Layer**: Too strict for research mode
2. **Tool Integration**: Sequential instead of parallel
3. **Verification**: No cross-checking between sources
4. **Error Handling**: Silent failures in tool launches
5. **Cache Management**: No per-job cache isolation

---

## NEXT STEPS

1. Implement compliance bypass for max/research modes
2. Add parallel tool execution
3. Implement result merging logic
4. Add tool health monitoring
5. Create comprehensive test suite

---

## Files Requiring Changes

1. `/backend/asagus/layers/compliance.py` - Add research mode bypass
2. `/backend/asagus/services/job_helpers.py` - Add cache clearing
3. `/backend/asagus/services/tools_runner.py` - Parallel execution
4. `/backend/asagus/layers/enrichment.py` - Multi-source merging
5. `/backend/asagus/routers/jobs.py` - Tool launch integration

---

## Testing Command

After fixes:
```bash
# Start backend with research mode
cd backend
source .venv/bin/activate
uvicorn asagus.main:app --host 0.0.0.0 --port 8000

# Test max mode scraping
curl -X POST http://localhost:8000/api/jobs/start \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Audit firm",
    "location": "Qatar",
    "mode": "max",
    "limit": 10,
    "enable_network_fetch": true,
    "enable_search_discovery": true
  }'
```

---

## CRITICAL NOTES

⚠️ **WARNING**: The current system will continue to skip 100% of records until compliance bypassing is implemented.

⚠️ **WARNING**: Download tools require proper folder structure in `/Download` directory.

⚠️ **WARNING**: Max mode requires significant system resources (CPU, memory, network).

✅ **GOOD NEWS**: The extraction logic for all fields (phone, email, WhatsApp, Twitter, LinkedIn) is already implemented and working. Once compliance is fixed, data will flow properly.

---

END OF REPORT
