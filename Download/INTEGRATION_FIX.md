# Download Tools Integration Fix

## Overview

This document outlines the comprehensive integration fix for all Download tools to work perfectly with the main ASAGUS scraper.

## Tools Inventory

### Active Tools (11 total)

1. **maps-scraper** - Google Maps business scraper
2. **outreach-scraper** - Contact information scraper  
3. **outreach-system** - Lead scoring and outreach pipeline
4. **outreach** - Outreach mailer system
5. **agent-reach** - Outreach channel doctor
6. **scrapegraph-ai** - LLM-powered extraction
7. **scrapling** - Adaptive parser
8. **firecrawl** - Hosted scraping API
9. **maxun** - Visual scraper
10. **scrapy** - Crawler framework
11. **whatsapp-detector** - WhatsApp number validation

## Integration Issues & Fixes

### Issue #1: Tools Run in Isolation
**Problem**: Tools don't share data with main scraper
**Fix**: Unified CSV output + data merging pipeline (already implemented in csv_merger.py)

### Issue #2: Environment Variables Not Shared
**Problem**: Tools don't have access to main scraper's LLM config, proxies, etc.
**Fix**: Environment propagation system (new)

### Issue #3: Browser-Based Tools Conflict
**Problem**: maps-scraper and outreach-scraper both launch browsers, causing resource conflicts
**Fix**: Browser pool coordination (new)

### Issue #4: Error Handling Inconsistent
**Problem**: Tool failures don't report properly to main scraper
**Fix**: Standardized error reporting (new)

### Issue #5: No Dependency Management
**Problem**: Tools may have missing dependencies
**Fix**: Dependency checker and auto-installer (new)

## Implementation Plan

### Phase 1: Enhanced Tool Launcher ✅ (Already Implemented)
- `asagus_tool_launcher.py` handles basic launching
- JSON output format
- Timeout handling

### Phase 2: Environment Propagation (NEW)
- Share LLM config from main scraper
- Share proxy URLs
- Share stealth mode settings

### Phase 3: Browser Pool Coordination (NEW)
- Limit concurrent browser instances
- Queue browser-based tools
- Share browser contexts when possible

### Phase 4: Dependency Management (NEW)
- Check tool dependencies before launch
- Auto-install missing packages
- Cache installation results

### Phase 5: Enhanced Error Reporting (NEW)
- Standardized error format
- Retry logic for transient failures
- Graceful degradation

## Files to Create/Modify

1. **enhanced_tool_coordinator.py** (NEW) - Main coordinator
2. **tool_dependency_manager.py** (NEW) - Dependency checker
3. **tool_browser_pool.py** (NEW) - Browser resource manager
4. **asagus_tool_launcher.py** (ENHANCE) - Add environment propagation
5. Individual tool wrappers (ENHANCE) - Standardize interfaces

## Quick Fixes for Immediate Use

### 1. Enable Real Runs
```bash
export ASAGUS_TOOL_REAL_RUN=1
```

### 2. Share LLM Config
```bash
export ANTHROPIC_API_KEY="your-key-here"
export LLM_PROVIDER="anthropic"
export LLM_MODEL="claude-3-5-sonnet-20241022"
```

### 3. Share Proxy Config
```bash
export RESIDENTIAL_PROXY_URL="http://user:pass@host:port"
```

### 4. Limit Concurrent Browsers
```bash
export ASAGUS_MAX_CONCURRENT_BROWSERS=2
```

## Tool-Specific Fixes

### maps-scraper
**Status**: ✅ Working
**Dependencies**: playwright, asyncio
**Fix Needed**: None - already integrated

### outreach-scraper
**Status**: ✅ Working
**Dependencies**: playwright, asyncio
**Fix Needed**: None - already integrated

### outreach-system  
**Status**: ✅ Working (dry-run only by default)
**Dependencies**: Flask, smtplib
**Fix Needed**: None - intentionally dry-run for safety

### scrapegraph-ai
**Status**: ⚠️ Needs LLM config
**Dependencies**: scrapegraphai, LLM API keys
**Fix Needed**: Environment propagation

### scrapling
**Status**: ✅ Working
**Dependencies**: scrapling (already installed in main venv)
**Fix Needed**: None

### firecrawl
**Status**: ⚠️ Needs API key
**Dependencies**: FIRECRAWL_API_KEY
**Fix Needed**: Environment check + clear error message

### maxun
**Status**: ⚠️ Node.js project
**Dependencies**: Node.js, npm packages
**Fix Needed**: Node environment setup

### whatsapp-detector
**Status**: ⚠️ Node.js project
**Dependencies**: Node.js, npm packages  
**Fix Needed**: Node environment setup

### agent-reach
**Status**: ✅ Working
**Dependencies**: Python packages
**Fix Needed**: None

### scrapy
**Status**: ✅ Working
**Dependencies**: scrapy (already installed)
**Fix Needed**: None

### outreach
**Status**: ✅ Working
**Dependencies**: Flask, email libraries
**Fix Needed**: None

## Testing Checklist

- [ ] All Python tools launch successfully
- [ ] All tools receive job context (query, location, limit)
- [ ] All tools output to correct directory (.asagus-runs/<job-id>/)
- [ ] CSV merger combines all tool outputs
- [ ] Deduplication works across tools
- [ ] LLM config shared with scrapegraph-ai
- [ ] Browser tools respect concurrent limit
- [ ] Node.js tools work (maxun, whatsapp-detector)
- [ ] Error messages are clear and actionable
- [ ] Timeout handling works properly

## Next Steps

1. ✅ Phase 1: Basic launcher (done)
2. 🔄 Phase 2: Environment propagation (in progress)
3. ⏳ Phase 3: Browser coordination (planned)
4. ⏳ Phase 4: Dependency management (planned)
5. ⏳ Phase 5: Error reporting (planned)
