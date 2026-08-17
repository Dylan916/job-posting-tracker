# InternIndex ⚡ — Real-Time Internship & Engineering Registry

An automated data engineering pipeline, multi-ATS watcher, and real-time alert system that ingests tech internship postings across aggregators and direct company ATS APIs (Greenhouse, Ashby, Lever), detects new openings via idempotent PostgreSQL diffing, and dispatches sub-second alerts (Telegram bot + Web Dashboard).

> **⚡ 100% Autonomous & Background-First:** InternIndex operates continuously in the background as a self-hosted daemon or Dagster cron pipeline. You never need to keep a browser open or manually refresh spreadsheets—the system monitors 3,000+ companies while you code, study, or sleep, and pings your phone the instant a target role opens.

![InternIndex Web Dashboard](docs/assets/dashboard.png)

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion ["1. Multi-Source Ingestion Engine"]
        S1["SimplifyJobs (Summer 2027 listings)\n• HTTP ETag Caching (0.05s)"] --> Base["SourcePoller Base Class\n(Jittered Exponential Backoff)"]
        S2["Direct ATS APIs (Greenhouse / Ashby / Lever)\n• Anthropic, Figma, Stripe, Palantir, Perplexity..."] --> Base
    end

    subgraph Storage ["2. PostgreSQL 16 (Docker)"]
        Base --> Upsert["Idempotent Upsert Engine\n(ON CONFLICT DO UPDATE)"]
        Upsert --> DB[("PostgreSQL 16\n• postings (15,500+ rows)\n• users & subscriptions\n• watched_companies\n• notifications_sent")]
    end

    subgraph Orchestration ["3. Dagster Orchestration (:3000)"]
        A1["raw_simplify_postings"] --> A3["upserted_postings_db"]
        A2["raw_custom_ats_postings"] --> A3
        A3 --> A4["telegram_alerts_dispatched"]
        Schedule["15-Min Automated Cron"] --> A1
    end

    subgraph ServiceLayer ["4. FastAPI Service Layer (:8000)"]
        DB --> API["FastAPI Backend Application\n• Connection Pooling (autocommit)\n• Full-Text GIN Search"]
        API --> Postings["/api/v1/postings (Search & Pagination)"]
        API --> Stats["/api/v1/stats (Live Aggregations)"]
    end

    subgraph UserInterfaces ["5. Multi-Channel User Interfaces"]
        Postings --> Web["InternIndex Web Dashboard (Minimalist UI)\n• Summer 2027 1-Click Apply\n• Single-Column Tracklist"]
        A4 --> Bot["Telegram Bot (@dylan_job_tracker_bot)\n• /watch term Summer 2027\n• /add_company ramp\n• /find Summer 2027"]
    end
```

---

## ✨ Key Features

1. **Multi-Source Ingestion & Zero-Load ETag Caching:**
   * Ingests 15,000+ tech listings from SimplifyJobs GitHub repositories (`Summer 2027`) and direct ATS public JSON feeds (Greenhouse, Ashby, Lever) in seconds.
   * Uses `If-None-Match: <etag>` HTTP caching on GitHub: completes in **0.058s (`HTTP 304 Not Modified`) with 0 bytes transferred and 0 database load** when unmodified.
2. **Custom Company ATS Watcher & Auto-Detection:**
   * Track any company's direct job board independent of Simplify:
     * 🟢 **Greenhouse:** Anthropic, Figma, Scale AI, Stripe, Datadog, Cloudflare, Airbnb, Anduril
     * 🔷 **Ashby:** Perplexity, Modal, Linear, Ramp, Cursor
     * 🔶 **Lever:** Palantir, Spotify, Netflix
   * Smart auto-detection via Telegram (`/add_company <name>`) and CLI (`uv run python scripts/check_company.py <name>`).
3. **Idempotent Storage & Change-Data-Capture:**
   * Uses PostgreSQL `INSERT INTO postings ... ON CONFLICT (source, external_id) DO UPDATE ... RETURNING (xmax = 0) AS is_new` to reliably identify brand-new job postings without duplicates.
4. **Minimalist Web Dashboard ("Roles" Design System):**
   * High-contrast, editorial interface served at `http://localhost:8000/`.
   * **Palette:** `#FAFAF8` (soft off-white), `#1A1A18` (text), `#6B6A63` (muted), `#2B4C3F` (deep pine green), `#E3E1D9` (hairline borders).
   * **Layout:** Plain stacked numerals (Summer 2027: 500+, Active: 3,000, Companies: 500+), text tabs with active underline, single-column job list with bold company, regular role title, right-aligned mono metadata, degree & location toggles (`[Undergrad Only]`, `[US Only]`, `[Remote Only]`), and direct `Apply ↗` CTAs.
5. **Real-Time Telegram Push Alerts:**
   * Interactive bot (`@dylan_job_tracker_bot`) with instantaneous push alerts and multi-keyword tracking.
   
   <p align="center">
     <img src="docs/assets/telegram_bot.png" width="400" alt="Telegram Bot Alerts" />
   </p>

6. **Data Orchestration with Dagster:**
   * Software-Defined Assets (SDAs) and 15-minute recurring automated schedules visible in Dagster UI at `http://localhost:3000/`.
   
   ![Dagster Automated Pipeline](docs/assets/dagster_pipeline.gif)

---

## 🚀 Quickstart (Running Locally on macOS / Linux)

### 1. Start PostgreSQL Database
```bash
docker compose up -d
```

### 2. Install Dependencies & Initialize Database
```bash
uv sync
uv run python db/init_db.py
```

### 3. Start Services

#### **Option A: 1-Command Launcher (Recommended)**
Start PostgreSQL, the FastAPI Web Dashboard, Dagster Orchestration, and the Telegram Bot concurrently with graceful `Ctrl + C` shutdown:

```bash
./start.sh
# or
make dev
```

![1-Command Terminal Startup](docs/assets/terminal_startup.gif)

#### **Option B: Manual Multi-Terminal Execution**
If you prefer running services in separate terminal windows:

```bash
# Terminal 1: FastAPI Backend & Web Dashboard (Port 8000)
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Dagster Automated Pipeline (Port 3000)
uv run dagster dev -f orchestration/definitions.py -p 3000

# Terminal 3: Telegram Alert Bot Daemon
uv run python -m notifications.bot
```

* **⚡ Web Dashboard:** [http://localhost:8000](http://localhost:8000)
* **📡 Interactive API Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **📊 Dagster Pipeline Graph:** [http://localhost:3000](http://localhost:3000)
* **🤖 Telegram Bot:** Connect to `@dylan_job_tracker_bot`

---

## 🤖 Telegram Bot Commands Reference

| Command | Description | Example |
| :--- | :--- | :--- |
| `/start` | Register user and initialize subscription. | `/start` |
| `/find <query> [count]` | Search active postings by role, keyword, or company. | `/find Summer 2027 10` |
| `/watch term <term>` | Subscribe to new postings for a recruiting season. | `/watch term Summer 2027` |
| `/watch <company>` | Subscribe to all new postings from a specific company. | `/watch Stripe` |
| `/watch keyword <keyword>`| Subscribe to postings containing a keyword. | `/watch keyword Machine Learning` |
| `/add_company <name>` | Auto-detect and track a company's direct ATS board. | `/add_company ramp` |
| `/companies` | List all tracked custom ATS company boards. | `/companies` |
| `/mode <instant\|digest\|pause>` | Set notification delivery mode (instant alerts, daily digest, or pause). | `/mode digest` |
| `/list` | View your active subscriptions. | `/list` |
| `/unwatch <id\|all>` | Remove a subscription. | `/unwatch all` |

### 🔔 Notification Delivery Modes:
* **⚡ `instant` (Default):** Dispatches sub-second Telegram alerts immediately when a new matching posting is detected.
* **🗞️ `digest` (Daily Summary):** Batches new openings into a daily digest with highlighted top roles and a 1-click dashboard link.
* **⏸️ `pause`:** Temporarily silences notifications without deleting your subscriptions.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/v1/postings` | `GET` | Paginated search filtering by `term`, `company`, `keyword`, `is_remote`, and `is_active`. |
| `/api/v1/postings/{id}` | `GET` | Retrieve full posting metadata and raw JSON. |
| `/api/v1/stats` | `GET` | Real-time counts across data sources, recruiting terms, and top companies. |
| `/api/v1/health` | `GET` | Database connection pool readiness probe. |

---

## 🖥️ Production Self-Hosting (Arch Linux / Home NUC)

For 24/7 continuous operation on a home server or Arch Linux mini-PC using systemd and Docker Compose, check out the [Production Deployment Guide](file:///Users/dylanlouie/Projects/job-posting-tracker/deploy/README.md).
