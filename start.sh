#!/usr/bin/env bash
# ==============================================================================
# InternIndex — Unified Multi-Service Launch Script
# Launches PostgreSQL, FastAPI Web Dashboard, Dagster Pipelines, and Telegram Bot
# ==============================================================================

set -e

# ANSI Color Tokens
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${CYAN}⚡ Starting InternIndex Platform...${NC}\n"

# 1. Start PostgreSQL via Docker if not already running
echo -e "${YELLOW}1/4 Checking PostgreSQL container...${NC}"
docker compose up -d

# 2. Trap SIGINT (Ctrl+C) and SIGTERM for instantaneous shutdown
cleanup() {
    trap - SIGINT SIGTERM EXIT
    echo -e "\n${YELLOW}Shutting down InternIndex services...${NC}"
    # Kill all spawned processes and child workers immediately
    if [ -n "$FASTAPI_PID" ]; then kill -9 "$FASTAPI_PID" 2>/dev/null || true; fi
    if [ -n "$DAGSTER_PID" ]; then kill -9 "$DAGSTER_PID" 2>/dev/null || true; fi
    if [ -n "$BOT_PID" ]; then kill -9 "$BOT_PID" 2>/dev/null || true; fi
    pkill -9 -f "notifications.bot" 2>/dev/null || true
    pkill -9 -f "orchestration/definitions.py" 2>/dev/null || true
    pkill -9 -f "uvicorn api.main:app" 2>/dev/null || true
    echo -e "${GREEN}✓ All services stopped cleanly.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 3. Start FastAPI Backend & Web Dashboard (Port 8000)
echo -e "${YELLOW}2/4 Starting FastAPI Backend & Web Dashboard on :8000...${NC}"
uv run uvicorn api.main:app --host 127.0.0.1 --port 8000 &
FASTAPI_PID=$!

# 4. Start Dagster Orchestration Dev Webserver (Port 3000)
echo -e "${YELLOW}3/4 Starting Dagster Orchestration Pipeline on :3000...${NC}"
uv run dagster dev -f orchestration/definitions.py -p 3000 --host 127.0.0.1 &
DAGSTER_PID=$!

# 5. Start Telegram Alert Bot Daemon
echo -e "${YELLOW}4/4 Starting Telegram Bot Listener Daemon...${NC}"
uv run python -m notifications.bot &
BOT_PID=$!

sleep 3

echo -e "\n${BOLD}${GREEN}======================================================${NC}"
echo -e "${BOLD}${GREEN}🚀 InternIndex is Live and Running!${NC}"
echo -e "${BOLD}${GREEN}======================================================${NC}"
echo -e "• ${BOLD}⚡ Web Dashboard:${NC}       ${CYAN}http://localhost:8000${NC}"
echo -e "• ${BOLD}📡 API Docs (Swagger):${NC}   ${CYAN}http://localhost:8000/docs${NC}"
echo -e "• ${BOLD}📊 Dagster Pipeline DAG:${NC} ${CYAN}http://localhost:3000${NC}"
echo -e "• ${BOLD}🤖 Telegram Alert Bot:${NC}   ${CYAN}https://t.me/dylan_job_tracker_bot${NC}"
echo -e "${BOLD}${GREEN}======================================================${NC}"
echo -e "${YELLOW}👉 Hold [Cmd / Ctrl] and click any link above to open in your browser!${NC}"
echo -e "${YELLOW}Press [Ctrl + C] once anytime to stop all services cleanly.${NC}\n"

# Wait for all background jobs
wait
