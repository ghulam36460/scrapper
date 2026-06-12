# ASAGUS Mailer v2.0

Production-grade cold email automation system. Manages multiple sender accounts, CSV leads, A/B tested campaigns, follow-ups, reply detection, inbox warmup, spam scoring, and deep analytics.

---

## Setup

### 1. Backend

```bash
cd asagus-mailer/backend
pip install -r requirements.txt
```

Start the API:
```bash
cd asagus-mailer
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

On first run, a `.env` file is auto-created with a generated `SECRET_KEY`.  
The SQLite database (`asagus.db`) is also auto-created with all tables.

### 2. Frontend

```bash
cd asagus-mailer/frontend
npm install
npm run dev
```

Frontend runs at: **http://localhost:3000**  
Backend API docs at: **http://localhost:8000/docs**

---

## Generate SECRET_KEY (if needed manually)

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the result into `.env`:
```
SECRET_KEY=your_generated_key_here
```

---

## Gmail Setup

1. Go to Google Account → Security → 2-Step Verification → **App Passwords**
2. Generate an App Password for "Mail"
3. Use this App Password (not your account password) in ASAGUS
4. Enable IMAP in Gmail Settings → Forwarding and POP/IMAP

---

## Email Template Variables

| Variable | Description |
|---|---|
| `{{name}}` | Lead's name (fallback: "there") |
| `{{business}}` | Business name (fallback: "your business") |
| `{{sender_name}}` | Your display name |
| `{{unsubscribe_link}}` | Unique unsubscribe URL (required) |

---

## Architecture

```
Backend  → FastAPI + SQLAlchemy (async) + SQLite WAL
Scheduler → APScheduler (IMAP poll every 5min, follow-ups every 15min)
Security  → Fernet encryption for all passwords at rest
Frontend  → Next.js 16 + Tailwind CSS + Recharts
```

---

## Features

- ✅ Multi-sender rotation with daily limits
- ✅ CSV upload with auto-column detection & 3-level dedup  
- ✅ A/B subject line testing with reply tracking
- ✅ Day 3 / Day 6 follow-up sequences
- ✅ 4-layer IMAP reply matching (Message-ID, subject similarity, sender, thread)
- ✅ Bounce detection & auto-unsubscribe from reply keywords
- ✅ Inbox warmup (10-day gradual ramp)
- ✅ Pure Python spam score checker (14 rules)
- ✅ Token-based legal unsubscribe links
- ✅ Campaign-level per-sender limits
- ✅ Full analytics: timeline, A/B results, per-campaign/template/sender

---

## Security

- Passwords encrypted with Fernet before SQLite storage
- Secret key in `.env` only (never in code or DB)
- `.env` and `*.db` files in `.gitignore`
- Decrypted passwords never returned via API
