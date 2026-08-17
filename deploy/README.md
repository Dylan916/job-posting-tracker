# Production Deployment & Self-Hosting Guide (Arch Linux / Home NUC)

This guide walks through deploying the **InternPulse** job tracking pipeline and web dashboard to a home mini-PC / NUC running Arch Linux (or Ubuntu/Debian) for 24/7 continuous operation.

---

## 1. Prerequisites on the NUC

Ensure Docker and `uv` (Fast Python package manager) are installed:

```bash
# 1. Update system & install Docker & git
sudo pacman -Syu docker docker-compose git

# 2. Enable and start Docker service
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

# 3. Install Astral uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or source ~/.zshrc
```

---

## 2. Clone Repository & Configure Environment

```bash
# Clone the repository
git clone https://github.com/Dylan916/job-posting-tracker.git ~/job-posting-tracker
cd ~/job-posting-tracker

# Create .env from template
cp .env.example .env
```

Edit `.env` with your Telegram Bot Token:
```ini
DATABASE_URL=postgresql://tracker_user:tracker_password@localhost:5432/job_tracker
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
SIMPLIFY_GITHUB_URL=https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json
```

---

## 3. Launch PostgreSQL Database

```bash
# Start PostgreSQL container
docker compose -f deploy/docker-compose.prod.yml up -d

# Verify container is healthy
docker ps
```

---

## 4. Run Initial Ingestion & Skill Extraction

```bash
# Install dependencies & initialize DB tables
uv sync

# Run initial ingestion to populate PostgreSQL
uv run python -m ingestion.runner

# Run skill extraction & ATS description enrichment
uv run python -m processing.extractor
```

---

## 5. Enable Systemd Services (24/7 Auto-Restart on Boot)

Copy the systemd service to `/etc/systemd/system/`:

```bash
# Copy service unit
sudo cp deploy/job-tracker.service /etc/systemd/system/job-tracker@.service

# Enable and start the service under your user
sudo systemctl daemon-reload
sudo systemctl enable --now job-tracker@$USER.service

# Check service status
sudo systemctl status job-tracker@$USER.service
```

---

## 6. Accessing the Services on your Local Network

* **Web Dashboard:** `http://<NUC_LOCAL_IP>:8000/`
* **FastAPI Swagger Docs:** `http://<NUC_LOCAL_IP>:8000/docs`
* **Telegram Bot:** Active 24/7 in the cloud (`@dylan_job_tracker_bot`)
