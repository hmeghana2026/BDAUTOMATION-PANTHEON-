# BD Automation Platform

Zero-cost, fully automated business development platform for Restaurants, Vets, and Dermatologists.

## Features

- **Lead Research** — Scrapes websites via Firecrawl + BeautifulSoup, extracts contacts with LLM, verifies emails via Hunter.io
- **Email Automation** — Personalized cold emails via Groq (Llama 3.1 70B) with Gemini fallback, auto-sent via Resend
- **5-Touch Follow-up** — Automated sequences (Day 0, 3, 7, 10, 14) via Celery beat
- **Meeting → PRD** — Transcribes audio (Whisper/AssemblyAI), generates structured PRDs, builds HTML prototypes
- **Streamlit Dashboard** — Kanban pipeline, email management, analytics

## Tech Stack (All Free Tier)

| Service | Purpose | Free Limit |
|---------|---------|-----------|
| Groq (Llama 3.1 70B) | Primary LLM | 14,400 req/day |
| Google Gemini 1.5 Flash | Fallback LLM | 1M tokens/day |
| Supabase | Postgres DB | 500MB |
| Firecrawl | Web scraping | 500 pages/month |
| Resend | Email sending | 100 emails/day |
| Hunter.io | Email verification | 25 searches/month |
| Railway.app | Deployment | 500 hours/month |
| Streamlit Cloud | Dashboard | Unlimited |

## Setup

### 1. Clone & Install

```bash
git clone <repo>
cd bd-automation
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required:**
- `GROQ_API_KEY` — [console.groq.com](https://console.groq.com)
- `GEMINI_API_KEY` — [aistudio.google.com](https://aistudio.google.com)
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` — [supabase.com](https://supabase.com)
- `RESEND_API_KEY` — [resend.com](https://resend.com)
- `FROM_EMAIL` + `FROM_NAME` — Your verified sender identity

**Optional (but recommended):**
- `FIRECRAWL_API_KEY` — Falls back to BeautifulSoup if blank
- `HUNTER_API_KEY` — Email verification skipped if blank
- `REDIS_URL` — Required for Celery (Railway Redis add-on)

### 3. Database Migration

Run this SQL in your Supabase SQL editor:

```sql
-- Contents of database/migrations/001_initial_schema.sql
```

### 4. Run Locally

```bash
# Start Streamlit dashboard
streamlit run app.py

# Start Celery worker (separate terminal)
celery -A tasks worker --loglevel=info

# Start Celery beat scheduler (separate terminal)
celery -A tasks beat --loglevel=info
```

### 5. Deploy to Railway

```bash
railway login
railway init
railway add --plugin redis  # Add Redis for Celery
railway up
```

Set all environment variables in Railway dashboard under Variables.

## Usage Flow

1. **Add Lead** → Dashboard → Add Lead form
2. **Auto-research** triggers within 30 min (Celery) or immediately if checked
3. **Email drafted** automatically for researched leads with verified contacts
4. **Auto-sent** at 9 AM UTC daily (Option C — fully autonomous)
5. **Follow-ups** fire on Day 3, 7, 10 automatically
6. **Dead** — leads with no reply after Day 14 are auto-marked dead

## Email Limits

- Hard cap: **50 emails/day** (preserves domain reputation)
- Sending time: **9 AM UTC** daily
- Between-request delay: **2 seconds** (scraping)

## File Structure

```
bd-automation/
├── agents/
│   ├── lead_research.py     # Web scraping + LLM extraction
│   ├── email_drafter.py     # Personalized email generation
│   ├── followup.py          # 5-touch follow-up automation
│   └── prd_generator.py     # Meeting transcript → PRD
├── database/
│   ├── models.py            # Pydantic models
│   ├── supabase_client.py   # Database wrapper
│   └── migrations/
│       └── 001_initial_schema.sql
├── integrations/
│   ├── groq_client.py
│   ├── gemini_client.py
│   ├── resend_client.py
│   ├── firecrawl_client.py
│   └── hunter_client.py
├── templates/
│   ├── email_templates.json
│   └── prd_template.md
├── tasks.py                 # Celery background tasks
├── app.py                   # Streamlit dashboard
├── requirements.txt
├── .env.example
├── railway.json
└── Procfile
```
