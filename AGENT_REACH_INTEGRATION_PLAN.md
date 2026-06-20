# Agent-Reach Deep Integration Plan

## 🎯 Goal

Fully integrate Agent-Reach into ASAGUS Scraper v3 so that:
1. **Agent-Reach's 15+ channels** (Twitter, Reddit, YouTube, GitHub, etc.) enrich business data
2. **Configuration UI** in ASAGUS frontend for setting up API keys, cookies, etc.
3. **MAX mode** automatically uses Agent-Reach to find additional contact info
4. **Real scraping** with CSV outputs containing enriched data

---

## 📊 Agent-Reach Capabilities (From Docs)

### Channels That Can Enrich Business Data

| Channel | Use for ASAGUS | Configuration Needed |
|---------|----------------|---------------------|
| 🌐 **Web** | Scrape business websites | None (Jina Reader free) |
| 🐦 **Twitter** | Find business Twitter handles | Cookie |
| 📖 **Reddit** | Find business mentions | Cookie |
| 📦 **GitHub** | Find company GitHub repos | Optional token |
| 💼 **LinkedIn** | Find company LinkedIn pages | Cookie (via MCP) |
| 📕 **小红书** | Find Chinese businesses | Cookie |
| 💬 **WeChat** | Find WeChat official accounts | None (Exa search) |
| 📰 **Weibo** | Find Weibo accounts | None |
| 💻 **V2EX** | Find tech companies | None |
| 🔍 **Exa Search** | General web search | MCP (free) |
| 📡 **RSS** | Monitor business blogs | None |

### What Agent-Reach CAN'T Do

- ❌ Extract phone numbers directly
- ❌ Extract email addresses directly  
- ❌ Scrape Google Maps
- ✅ BUT can scrape business websites to find contact info
- ✅ Find social media profiles
- ✅ Extract content from various platforms

---

## 🏗️ Implementation Architecture

### Phase 1: Real Agent-Reach Adapter (Working Scraper)

**File**: `Download/Agent-Reach-main/asagus_adapter.py`

**What it will do**:
1. Receive ASAGUS job context (query, location, limit)
2. Use Agent-Reach's web channel to scrape business websites
3. Use Exa search to find businesses
4. Extract available data (name, website, social profiles)
5. Output to CSV in ASAGUS format

### Phase 2: Configuration API

**Files**:
- `asagus-scraper-v3/backend/asagus/routers/agent_reach.py` (new)
- `asagus-scraper-v3/backend/asagus/services/agent_reach_config.py` (new)

**Endpoints**:
- `GET /api/agent-reach/status` - Check which channels are configured
- `POST /api/agent-reach/config/twitter` - Set Twitter cookie
- `POST /api/agent-reach/config/reddit` - Set Reddit cookie
- `POST /api/agent-reach/config/github` - Set GitHub token
- `GET /api/agent-reach/channels` - List all available channels
- `POST /api/agent-reach/test/{channel}` - Test if channel works

### Phase 3: Frontend Configuration UI

**Files**:
- `asagus-scraper-v3/frontend/app/agent-reach/page.tsx` (new)
- `asagus-scraper-v3/frontend/components/agent-reach-config.tsx` (new)

**UI Components**:
1. **Channel Status Dashboard** - Shows which channels are ready
2. **Configuration Forms** - Input cookies, API keys, tokens
3. **Test Buttons** - Test each channel before saving
4. **Usage Stats** - Show how many times each channel was used

### Phase 4: MAX Mode Integration

**Modified**: `asagus-scraper-v3/backend/asagus/main.py`

**Logic**:
1. Primary scraper finds businesses
2. For each business found:
   - Agent-Reach web channel scrapes their website
   - Extracts additional contact info from website
   - Searches for their social media profiles
   - Enriches the record with found data

---

## 🔧 Implementation Steps

### Step 1: Install Agent-Reach in Backend

```bash
cd asagus-scraper-v3/backend
.venv/bin/pip install agent-reach
```

### Step 2: Real Agent-Reach Adapter

Create adapter that:
- Uses Exa search to find businesses based on query
- Uses Jina Reader to scrape business websites
- Extracts contact information
- Outputs CSV with enriched data

### Step 3: Backend Configuration Service

Create service that:
- Stores Agent-Reach configuration (cookies, tokens)
- Validates configuration
- Tests each channel
- Provides configuration to adapter

### Step 4: Frontend Configuration Page

Create UI that:
- Shows all Agent-Reach channels
- Allows configuration of each channel
- Tests channels before use
- Shows status (ready/not ready/needs config)

### Step 5: MAX Mode Enrichment

Integrate into main scraping loop:
- After primary scraping, call Agent-Reach
- Enrich records with additional data
- Merge results intelligently

---

## 📝 Example Flow

### User Configures Agent-Reach (One-Time)

1. User opens ASAGUS frontend
2. Navigates to "Tools → Agent-Reach Configuration"
3. Sees dashboard with 15 channels
4. Clicks "Configure Twitter"
5. Pastes cookie from Cookie-Editor extension
6. Clicks "Test" - sees "✅ Twitter ready"
7. Repeats for other channels they want to use

### MAX Mode Job Runs

1. User creates job: "restaurants in Doha Qatar", MAX mode
2. **Primary scraper** finds 100 restaurants
3. **Agent-Reach enrichment** (parallel):
   - For each restaurant:
     - Web channel: Scrape their website → extract email, phone from HTML
     - Exa search: Find their social profiles → Twitter, Facebook handles
     - GitHub: Check if they have GitHub (for tech businesses)
4. **Results merged**: Original data + Agent-Reach enrichment
5. **CSV export**: All fields populated with maximum data

### Example Output

```csv
name,phone,email,website,twitter,facebook,github,data_sources
"Al Majlis Restaurant","+974...",,"almajlis.qa","@almajlis_qa","fb.com/almajlis","","primary,agent-reach-web"
"Tech Startup Qatar","+974...","hello@tech.qa","tech.qa","@techqatar","","gh.com/techqatar","primary,agent-reach-web,agent-reach-github"
```

---

## ⏱️ Time Estimate

| Phase | Time | Complexity |
|-------|------|------------|
| Phase 1: Real adapter | 2-3 hours | Medium |
| Phase 2: Backend API | 1-2 hours | Low |
| Phase 3: Frontend UI | 2-3 hours | Medium |
| Phase 4: MAX mode integration | 1-2 hours | Low |
| **Total** | **6-10 hours** | **Medium-High** |

---

## 🚀 Let's Start

I'll begin with Phase 1: Creating a REAL Agent-Reach adapter that:
1. Actually installs and uses Agent-Reach
2. Scrapes business data using multiple channels
3. Outputs real CSV files with enriched data

Ready to implement?
