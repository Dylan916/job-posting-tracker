"""End-to-End Simulation Tests: Ingestion, Change-Data-Capture (CDC), and Alert Triggering."""

from typing import Any
from unittest.mock import MagicMock

from ingestion.models import NormalizedPosting
from notifications.matcher import matches_subscription


def simulate_cdc_upsert(
    existing_db: dict[tuple[str, str], dict[str, Any]],
    incoming_postings: list[NormalizedPosting],
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Simulate PostgreSQL's ON CONFLICT DO UPDATE RETURNING (xmax = 0) AS is_new logic in memory.
    Returns (newly_inserted_records, new_count, updated_count).
    """
    new_records: list[dict[str, Any]] = []
    new_count = 0
    updated_count = 0

    for p in incoming_postings:
        key = (p.source, p.external_id)
        is_new = key not in existing_db

        record = {
            "source": p.source,
            "external_id": p.external_id,
            "company": p.company,
            "title": p.title,
            "terms": ", ".join(p.terms) if p.terms else None,
            "location": p.location,
            "is_remote": p.is_remote,
            "is_active": p.is_active,
            "url": p.url,
            "is_new": is_new,
        }

        existing_db[key] = record

        if is_new:
            new_count += 1
            new_records.append(record)
        else:
            updated_count += 1

    return new_records, new_count, updated_count


def test_full_pipeline_cdc_lifecycle():
    """
    Simulate the complete 3-phase lifecycle:
    1. Initial Sync (2 jobs: Anthropic & Stripe) -> 2 new alerts
    2. Unchanged Polling -> 0 duplicate alerts
    3. Board Change (Amazon opens a new job) -> Exactly 1 alert dispatched ONLY for Amazon
    """
    simulated_db: dict[tuple[str, str], dict[str, Any]] = {}
    user_sub = {"term_filter": "Summer 2027", "company_filter": None, "keyword_filter": None, "location_filter": None}

    # -------------------------------------------------------------
    # Phase 1: Initial Sync with 2 Jobs
    # -------------------------------------------------------------
    job_anthropic = NormalizedPosting(
        source="ats_greenhouse",
        external_id="anthropic_001",
        company="Anthropic",
        title="AI Systems Intern",
        terms=["Summer 2027"],
        location="San Francisco, CA",
        is_active=True,
    )
    job_stripe = NormalizedPosting(
        source="ats_greenhouse",
        external_id="stripe_001",
        company="Stripe",
        title="Infrastructure Engineer Intern",
        terms=["Summer 2027"],
        location="Seattle, WA",
        is_active=True,
    )

    phase1_new, p1_new_cnt, p1_upd_cnt = simulate_cdc_upsert(simulated_db, [job_anthropic, job_stripe])

    assert p1_new_cnt == 2
    assert p1_upd_cnt == 0
    assert len(phase1_new) == 2

    # Check alert dispatch in Phase 1
    phase1_alerts = [j for j in phase1_new if matches_subscription(j, user_sub)]
    assert len(phase1_alerts) == 2
    assert {a["company"] for a in phase1_alerts} == {"Anthropic", "Stripe"}

    # -------------------------------------------------------------
    # Phase 2: Polling Cycle with NO changes (Unchanged)
    # -------------------------------------------------------------
    phase2_new, p2_new_cnt, p2_upd_cnt = simulate_cdc_upsert(simulated_db, [job_anthropic, job_stripe])

    assert p2_new_cnt == 0
    assert p2_upd_cnt == 2
    assert len(phase2_new) == 0

    # Check alert dispatch in Phase 2 -> Zero alerts sent!
    phase2_alerts = [j for j in phase2_new if matches_subscription(j, user_sub)]
    assert len(phase2_alerts) == 0, "Expected 0 duplicate alerts on unchanged run"

    # -------------------------------------------------------------
    # Phase 3: The Board Changes! (Amazon adds a brand-new Summer 2027 job)
    # -------------------------------------------------------------
    job_amazon = NormalizedPosting(
        source="ats_greenhouse",
        external_id="amazon_001",
        company="Amazon",
        title="Software Development Engineer Intern",
        terms=["Summer 2027"],
        location="Seattle, WA",
        is_active=True,
    )

    phase3_new, p3_new_cnt, p3_upd_cnt = simulate_cdc_upsert(simulated_db, [job_anthropic, job_stripe, job_amazon])

    assert p3_new_cnt == 1
    assert p3_upd_cnt == 2
    assert len(phase3_new) == 1
    assert phase3_new[0]["company"] == "Amazon"

    # Check alert dispatch in Phase 3 -> Dispatches alert ONLY for Amazon!
    phase3_alerts = [j for j in phase3_new if matches_subscription(j, user_sub)]
    assert len(phase3_alerts) == 1
    assert phase3_alerts[0]["company"] == "Amazon"
    assert phase3_alerts[0]["title"] == "Software Development Engineer Intern"


def test_full_system_end_to_end_propagation():
    """
    Test complete end-to-end propagation across all 4 system layers:
    1. Ingestion discovers a new Summer 2027 job (Amazon).
    2. Change-Data-Capture (CDC) detects it as is_new=True and writes to Database.
    3. Notification Matcher dispatches instant Telegram alert to Summer 2027 subscribers.
    4. FastAPI Web Dashboard API immediately reflects the new job, updated count, and search results.
    """
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_db

    # Layer 1: Ingestion
    new_job = NormalizedPosting(
        source="simplify_github",
        external_id="amazon_sde_2027",
        company="Amazon",
        title="Software Development Engineer Intern - Summer 2027",
        terms=["Summer 2027"],
        location="Seattle, WA",
        is_remote=False,
        is_active=True,
        url="https://amazon.jobs/en/jobs/12345",
    )

    # Layer 2: CDC Database Upsert
    simulated_db: dict[tuple[str, str], dict[str, Any]] = {}
    new_records, new_cnt, upd_cnt = simulate_cdc_upsert(simulated_db, [new_job])

    assert new_cnt == 1
    assert len(new_records) == 1
    assert new_records[0]["company"] == "Amazon"

    # Layer 3: Telegram Notification Dispatch
    user_subscription = {"term_filter": "Summer 2027", "company_filter": None, "keyword_filter": None, "location_filter": None}
    alerts = [r for r in new_records if matches_subscription(r, user_subscription)]
    assert len(alerts) == 1
    assert alerts[0]["title"] == "Software Development Engineer Intern - Summer 2027"

    # Layer 4: FastAPI Web Dashboard & API Propagation
    now = datetime.now(timezone.utc)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"total": 1}
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "source": new_job.source,
            "external_id": new_job.external_id,
            "company": new_job.company,
            "title": new_job.title,
            "location": new_job.location,
            "terms": "Summer 2027",
            "is_remote": False,
            "url": new_job.url,
            "posted_at": now,
            "first_seen_at": now,
            "last_seen_at": now,
            "is_active": True,
        }
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    app.dependency_overrides[get_db] = lambda: mock_conn

    try:
        client = TestClient(app)
        api_res = client.get("/api/v1/postings?term=Summer%202027&is_undergrad_only=true")
        assert api_res.status_code == 200
        payload = api_res.json()

        # Verify web app receives the new job
        assert payload["total"] == 1
        assert payload["items"][0]["company"] == "Amazon"
        assert payload["items"][0]["url"] == "https://amazon.jobs/en/jobs/12345"
    finally:
        app.dependency_overrides.clear()
