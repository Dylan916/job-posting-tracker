# Real-Time Internship & Job Posting Tracker

An event-driven data engineering pipeline and alert system that ingests internship and job postings from multiple sources (SimplifyJobs GitHub aggregators and direct ATS JSON APIs like Greenhouse), detects new openings via idempotent diffing, matches them against subscriber watchlists, and dispatches real-time alerts via Telegram.

---

## Architecture & Features

* **Multi-Source Ingestion:** Ingests from SimplifyJobs GitHub repositories (`.github/scripts/listings.json`) and direct company Greenhouse ATS board endpoints (Cloudflare, Datadog, Stripe, etc.).
* **Idempotent Change Detection:** Uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE ... RETURNING (xmax = 0)` to reliably detect new postings and track existing ones without duplicate alerts.
* **Resilience & Fault Isolation:** Implements jittered exponential backoff for transient rate limits and dead-letter error logging for malformed records.
* **Telegram Bot Integration:** Interactive bot commands (`/start`, `/watch <company>`, `/watch keyword <term>`, `/mode <instant|digest|pause>`, `/list`, `/unwatch`).
* **Smart Notification Batching:** Consolidates multiple matching jobs into clean, batched Telegram messages.
* **Notification Preferences:** Supports instant real-time alerts, daily digests, and pausing.

---

## Project Structure

```
job-posting-tracker/
├── docker-compose.yml           # PostgreSQL 16 container
├── pyproject.toml               # Python dependencies (uv)
├── .env.example                 # Environment configuration template
├── .env                         # Local secrets
├── db/
│   ├── schema.sql               # PostgreSQL schema & GIN indexes
│   ├── connection.py            # Psycopg connection pool
│   └── init_db.py               # Table creation & migration runner
├── ingestion/
│   ├── models.py                # Pydantic data schemas
│   ├── base.py                  # Resilient SourcePoller base class
│   ├── simplify.py              # SimplifyJobs GitHub poller
│   ├── greenhouse.py            # Greenhouse ATS poller
│   └── runner.py                # Multi-source poller orchestrator
├── notifications/
│   ├── matcher.py               # Subscription filter matching engine
│   ├── dispatcher.py            # Telegram markdown dispatcher & batcher
│   └── bot.py                   # Telegram bot listener & command handlers
└── run_pipeline.py              # CLI entry point (once / loop / digest)
```

---

## Quickstart (Local Mac Dev)

### 1. Start PostgreSQL
```bash
docker compose up -d
```

### 2. Initialize Database Schema
```bash
uv run python -m db.init_db
```

### 3. Configure Telegram Bot Token (Optional for Live Notifications)
1. Message `@BotFather` on Telegram and create a bot (`/newbot`).
2. Copy the token and paste it into `.env`:
```ini
TELEGRAM_BOT_TOKEN="your_bot_token_here"
```
*(If no token is provided, the dispatcher runs in Mock Mode and prints formatted alerts to the terminal).*

### 4. Run the Telegram Bot Listener
In one terminal window, start the bot listener:
```bash
uv run python -m notifications.bot
```
Then open Telegram and send `/start` to your bot.

### 5. Run the Ingestion Pipeline
In another terminal, trigger a single poll & notify run:
```bash
uv run python run_pipeline.py --once
```
Or start continuous polling every 5 minutes:
```bash
uv run python run_pipeline.py --loop --interval 300
```
