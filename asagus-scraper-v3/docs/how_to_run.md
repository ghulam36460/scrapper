# How To Run ASAGUS Scraper 3.0

This guide is for Windows PowerShell from the project folder:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3
```

## 1. Requirements

Install these first:

- Node.js 20 or newer
- Python 3.12

Docker is optional. If you do not have Docker, use the local no-Docker setup below.

## 2. Fastest No-Docker Run

Open PowerShell in the project folder:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3
```

Create `.env`:

```powershell
Copy-Item .env.example .env
```

Keep these safe defaults in `.env`:

```env
ENABLE_NETWORK_FETCH=false
ENABLE_SEARCH_DISCOVERY=false
```

### Start Backend

In PowerShell window 1:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn asagus.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then try:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Start Frontend

In PowerShell window 2:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3\frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

API docs:

```text
http://localhost:8000/docs
```

### What Works Without Docker

No-Docker mode works with:

- GUI dashboard
- Job creation
- Offline safe scrape preview
- Policy engine
- Strong MDP scheduler
- Extraction cascade
- Enrichment
- In-memory records
- Hybrid search
- LLM provider setup
- Algorithm/capability views

These production stores are optional and not required for first run:

- Postgres
- Redis
- OpenSearch
- Qdrant
- Neo4j
- MinIO
- Prometheus
- Grafana

The app falls back to local in-memory runtime where possible.

## 3. Create Environment File

```powershell
Copy-Item .env.example .env
```

Default safety settings are:

```env
ENABLE_NETWORK_FETCH=false
ENABLE_SEARCH_DISCOVERY=false
```

Keep these `false` for first run. The app will use offline preview data so you can test the full pipeline safely.

## 4. Optional Docker Run

Skip this section if you do not have Docker.

```powershell
docker compose up -d --build
```

Open:

- Frontend GUI: http://localhost:3000
- API docs: http://localhost:8000/docs
- Grafana: http://localhost:3001
- Prometheus: http://localhost:9090
- MinIO console: http://localhost:9001
- Neo4j browser: http://localhost:7474

Check services:

```powershell
docker compose ps
```

View API logs:

```powershell
docker compose logs -f api
```

Stop everything:

```powershell
docker compose down
```

## 5. First GUI Test

1. Open http://localhost:3000
2. Go to `Setup`
3. Leave LLM disabled or add your own provider key
4. Go to `Run`
5. Use a small limit like `5`
6. Click `Start`
7. Watch progress in `Pipeline`
8. Check extracted rows in `Records`
9. Try `Search`

## 6. LLM Setup

You can add keys in the GUI under `Setup`.

Supported providers:

- Claude / Anthropic
- OpenAI / ChatGPT
- Azure OpenAI
- Google Gemini
- Mistral
- Groq
- Together
- OpenRouter
- OpenAI-compatible gateways
- Ollama
- Custom HTTP JSON gateway

For a key from an independent Claude platform, choose:

```text
Provider: Independent Claude / OpenAI-Compatible Gateway
Model: the exact model id from that platform, for example anthropic/claude-opus-4.6
API key: your gateway key
Base URL: the platform API base URL, usually ending in /v1
```

You can also put keys in `.env`, for example:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key-here
```

For an independent gateway:

```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=anthropic/claude-opus-4.6
LLM_API_KEY=your-gateway-key
LLM_BASE_URL=https://your-gateway.example.com/v1
```

Then restart:

```powershell
uvicorn asagus.main:app --reload --host 127.0.0.1 --port 8000
```

## 7. Enable Real Discovery And Fetching

Only enable this after reviewing compliance, robots rules, rate limits and provider terms.

In `.env`:

```env
ENABLE_SEARCH_DISCOVERY=true
ENABLE_NETWORK_FETCH=true
```

Then rebuild/restart:

```powershell
docker compose up -d --build
```

The system does not bypass auth, traps, blocks or honeypots. Those are quarantined for audit/manual review.

## 8. Local Development Without Docker

This is the same as the no-Docker run above, with extra notes.

Run backend:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn asagus.main:app --reload --host 0.0.0.0 --port 8000
```

Run frontend in another PowerShell:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3\frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## 9. Playwright Chromium

For real dynamic rendering outside Docker, install browser binaries:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3\backend
.\.venv\Scripts\Activate.ps1
python -m playwright install chromium
```

## 10. Useful API Checks

Health:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Algorithm state:

```powershell
Invoke-RestMethod http://localhost:8000/api/algorithm/state
```

Records:

```powershell
Invoke-RestMethod http://localhost:8000/api/records
```

## 11. Verification Commands

From the project root:

```powershell
cd C:\Users\Ghulam\Desktop\scrap\asagus-scraper-v3
python -m compileall backend\asagus
```

Frontend build:

```powershell
cd frontend
npm run build
```

## 12. Common Problems

Python install fails on a heavy package:

```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

If a model package is still difficult on Windows, you can comment out heavy optional packages temporarily and run the local safe pipeline. The core API uses fallbacks.

Port already in use:

```powershell
docker compose ps
```

Then stop the conflicting service or change the port in `docker-compose.yml`.

Frontend cannot reach API:

- Check API is running on http://localhost:8000
- Check `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Restart frontend

Docker build is slow:

- First build downloads Python and Node dependencies
- Later builds should be faster

Playwright/Chromium errors:

```powershell
python -m playwright install chromium
```

No real web results:

- Confirm `ENABLE_SEARCH_DISCOVERY=true`
- Confirm network access is available
- Keep `ENABLE_NETWORK_FETCH=false` if you only want discovery previews

## 13. Safe Defaults

The first run is intentionally safe:

- No real fetch traffic unless `ENABLE_NETWORK_FETCH=true`
- No search-engine discovery unless `ENABLE_SEARCH_DISCOVERY=true`
- No auth bypass
- No API session exploitation
- No honeypot unlocking
- No face identification
- Manual review for low-confidence or sensitive cases
