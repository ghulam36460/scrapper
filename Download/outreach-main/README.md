# ASAGUS Mailer v2.0 — Production Cold Email Automation

A complete, production-ready cold email automation system with multi-sender rotation, A/B testing, follow-ups, reply detection, inbox warmup, and deep analytics.

## 🚀 Features

- **Multi-Sender Management** — Rotate across Gmail, Zoho, Brevo, or custom SMTP accounts
- **Smart CSV Upload** — Auto-detect columns, 3-level deduplication
- **A/B Subject Testing** — Test multiple subject lines, track reply rates per variant
- **Automated Follow-ups** — Day 3 & Day 6 sequences with dedicated templates
- **Reply Detection** — 4-layer IMAP matching (Message-ID, subject similarity, sender match, thread heuristic)
- **Inbox Warmup** — Gradual sending schedule (5→40 emails over 10 days)
- **Spam Score Checker** — Pure Python heuristic scoring before sending
- **Legal Compliance** — Token-based unsubscribe links, keyword detection
- **Deep Analytics** — Campaign performance, template effectiveness, sender stats, A/B results
- **Secure** — Fernet encryption for all passwords, never stored in plaintext

## 📋 Requirements

- Python 3.11+
- Node.js 18+
- Windows/Linux/macOS

## 🔧 Installation

### 1. Clone Repository
```bash
cd "c:\shehwar projects\outreach"
```

### 2. Backend Setup
```bash
cd asagus-mailer\backend
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ..\frontend
npm install
```

### 4. Generate Encryption Key

The system will auto-generate a `SECRET_KEY` on first startup and save it to `.env`. Alternatively, generate manually:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Create `.env` in project root:
```
SECRET_KEY=your_generated_key_here
```

## ▶️ Running the Application

### Option 1: Use the Run Script (Recommended)

**Windows:**
```bash
start.bat
```

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manual Start

**Terminal 1 — Backend:**
```bash
cd asagus-mailer\backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd asagus-mailer\frontend
npm run dev
```

### Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 📖 Quick Start Guide

### 1. Add Sender Accounts
- Go to **Senders** page
- Click **Add Sender**
- Select provider (Gmail/Zoho/Brevo/Custom)
- Enter credentials (use App Passwords for Gmail)
- Test connection
- Enable warmup for new accounts (recommended 10 days before campaigns)

### 2. Upload Leads
- Go to **Leads** page
- Drag & drop CSV file
- Map columns (Email is required)
- Confirm import

### 3. Create Templates
- Go to **Templates** page
- Create templates for:
  - Initial emails
  - Follow-up Day 3 (optional)
  - Follow-up Day 6 (optional)
- Add multiple subject variants for A/B testing
- Include `{{unsubscribe_link}}` in body (required)
- Check spam score before saving

### 4. Launch Campaign
- Go to **Campaigns** page
- Click **New Campaign**
- Follow 5-step wizard:
  1. Name your campaign
  2. Select lead file + set limit (optional)
  3. Choose templates (initial + follow-ups)
  4. Select sender accounts + set per-sender limits
  5. Review and create
- Click **Run** to start sending

### 5. Monitor & Respond
- **Dashboard** — Real-time overview
- **Sent** — View all sent emails
- **Follow-ups** — Manage scheduled follow-ups
- **Replies** — Read and respond to replies inline
- **Analytics** — Track performance metrics

## 🔐 Security Notes

- **Passwords:** All SMTP/IMAP passwords are encrypted with Fernet before storage
- **SECRET_KEY:** Never commit `.env` to version control
- **Unsubscribe:** Every email includes a unique unsubscribe token
- **Data:** SQLite database stored locally, not transmitted

## 📊 Database

- **Engine:** SQLite with WAL mode
- **Location:** `asagus.db` in project root
- **Auto-created:** All tables created on first startup
- **Backup:** Copy `asagus.db` file to backup

## 🔄 Scheduler Jobs

The system runs 4 background jobs:

1. **IMAP Poll** — Every 5 minutes (reply detection)
2. **Follow-up Sender** — Every 15 minutes (send due follow-ups)
3. **Daily Reset** — Midnight Asia/Karachi (reset sender daily limits)
4. **Warmup** — 9 AM Asia/Karachi (send warmup emails)

## 🛠️ SMTP Provider Setup

### Gmail
1. Enable 2FA on your Google account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Enable IMAP: Gmail Settings → Forwarding and POP/IMAP → Enable IMAP
4. Use App Password (not your account password)

### Zoho
1. Use your Zoho account password or generate app-specific password
2. IMAP is enabled by default

### Brevo (formerly Sendinblue)
1. Get SMTP credentials from Brevo dashboard
2. No IMAP available — set IMAP to your reply inbox (Gmail/Zoho)
3. Higher daily limit (300 emails)

## 📈 Best Practices

1. **Warmup New Accounts** — Run 10-day warmup before campaigns
2. **Daily Limits** — Start with 20-40 emails/day per account
3. **Personalization** — Use `{{name}}` and `{{business}}` variables
4. **A/B Testing** — Test 2-3 subject variants per campaign
5. **Follow-ups** — Wait 3-6 days between follow-ups
6. **Spam Score** — Keep score below 5.0
7. **Unsubscribe** — Always include unsubscribe link
8. **Reply Monitoring** — Check replies daily, respond promptly

## 🐛 Troubleshooting

### Backend won't start
- Check Python version: `python --version` (need 3.11+)
- Verify all packages installed: `pip install -r requirements.txt`
- Check if port 8000 is available

### Frontend won't start
- Check Node version: `node --version` (need 18+)
- Delete `node_modules` and reinstall: `npm install`
- Check if port 3000 is available

### SMTP connection fails
- Verify credentials are correct
- For Gmail: Use App Password, not account password
- Check firewall/antivirus blocking SMTP ports
- Test connection in Senders page

### IMAP not detecting replies
- Verify IMAP credentials
- Check IMAP is enabled in email provider settings
- Wait 5 minutes for next poll cycle
- Manually trigger poll in Replies page

### Emails going to spam
- Run spam score check on templates
- Ensure proper personalization (`{{name}}`, `{{business}}`)
- Include unsubscribe link
- Warm up new accounts before campaigns
- Lower daily sending volume

## 📁 Project Structure

```
asagus-mailer/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── database.py          # SQLAlchemy setup
│   ├── models.py            # ORM models
│   ├── schemas.py           # Pydantic schemas
│   ├── crypto.py            # Password encryption
│   ├── scheduler.py         # APScheduler jobs
│   ├── routers/             # API endpoints
│   └── services/            # Business logic
├── frontend/
│   ├── app/                 # Next.js pages
│   ├── components/          # React components
│   └── lib/                 # API client
├── .env                     # SECRET_KEY (never commit)
├── .env.example             # Template
├── asagus.db                # SQLite database
└── README.md                # This file
```

## 🤝 Support

For issues or questions:
- Check troubleshooting section above
- Review API docs at http://localhost:8000/docs
- Check browser console for frontend errors
- Check terminal logs for backend errors

## 📝 License

Proprietary — ASAGUS (Muhammad) © 2025

---

**Built with:** FastAPI • Next.js • SQLAlchemy • Tailwind CSS • APScheduler
