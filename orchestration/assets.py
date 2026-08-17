"""Dagster Software-Defined Assets (SDAs) for the job posting and analytics pipeline."""

from typing import Any
from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset

from db.connection import get_db_connection
from ingestion.greenhouse import GreenhousePoller
from ingestion.models import NormalizedPosting
from ingestion.runner import upsert_postings
from ingestion.simplify import SimplifyPoller
from notifications.dispatcher import dispatch_notifications
from processing.extractor import extract_skills_from_posting, save_skill_mentions


@asset(
    group_name="ingestion",
    description="Fetches and normalizes raw internship listings from SimplifyJobs Summer 2027 repository.",
)
def raw_simplify_postings(context: AssetExecutionContext) -> list[NormalizedPosting]:
    """Ingest SimplifyJobs GitHub JSON."""
    poller = SimplifyPoller()
    postings, stats = poller.run()
    context.log.info(f"SimplifyJobs fetched {len(postings)} normalized postings.")
    return postings


@asset(
    group_name="ingestion",
    description="Fetches and normalizes postings from all custom watched company boards (Greenhouse, Lever, Ashby).",
)
def raw_custom_ats_postings(context: AssetExecutionContext) -> list[NormalizedPosting]:
    """Ingest custom company ATS public boards (Greenhouse, Lever, Ashby)."""
    from ingestion.ats_watcher import MultiATSPoller, load_all_watched_companies

    with get_db_connection() as conn:
        watched = load_all_watched_companies(conn)

    all_postings: list[NormalizedPosting] = []
    for co in watched:
        poller = MultiATSPoller(co["company_name"], co["ats_provider"], co["board_token"])
        postings, _ = poller.run()
        all_postings.extend(postings)
        context.log.info(f"ATS {co['company_name']} ({co['ats_provider']}:{co['board_token']}): fetched {len(postings)} postings.")
    return all_postings


@asset(
    group_name="storage",
    description="Idempotently upserts all normalized postings into PostgreSQL and identifies new job openings.",
)
def upserted_postings_db(
    context: AssetExecutionContext,
    raw_simplify_postings: list[NormalizedPosting],
    raw_custom_ats_postings: list[NormalizedPosting],
) -> MaterializeResult:
    """Upsert postings into PostgreSQL and return newly detected rows."""
    all_postings = raw_simplify_postings + raw_custom_ats_postings
    
    with get_db_connection() as conn:
        new_records, new_count, updated_count = upsert_postings(conn, all_postings)

    context.log.info(
        f"Database Upsert Complete: {new_count} new postings, {updated_count} updated postings."
    )

    return MaterializeResult(
        value=new_records,
        metadata={
            "total_processed": MetadataValue.int(len(all_postings)),
            "new_postings_count": MetadataValue.int(new_count),
            "updated_postings_count": MetadataValue.int(updated_count),
        },
    )


@asset(
    group_name="alerts",
    description="Matches newly inserted postings against user subscriptions and dispatches batched Telegram notifications.",
)
def telegram_alerts_dispatched(
    context: AssetExecutionContext,
    upserted_postings_db: list[dict[str, Any]],
) -> MaterializeResult:
    """Evaluate user subscriptions and dispatch Telegram alerts."""
    new_postings = upserted_postings_db or []
    sent_count = 0

    if new_postings:
        sent_count = dispatch_notifications(new_postings, mode="instant")
        context.log.info(f"Dispatched {sent_count} alerts for {len(new_postings)} new postings.")
    else:
        context.log.info("No new postings detected in this run; skipping notification dispatch.")

    return MaterializeResult(
        value=sent_count,
        metadata={
            "new_postings_evaluated": MetadataValue.int(len(new_postings)),
            "notifications_dispatched": MetadataValue.int(sent_count),
        },
    )


@asset(
    group_name="analytics",
    description="Extracts in-demand tech skills from newly ingested postings and saves to skill_mentions table.",
)
def extracted_skills_asset(
    context: AssetExecutionContext,
    upserted_postings_db: list[dict[str, Any]],
) -> MaterializeResult:
    """Extract and persist skills for new postings."""
    new_postings = upserted_postings_db or []
    total_mentions = 0

    if new_postings:
        with get_db_connection() as conn:
            for p in new_postings:
                skills = extract_skills_from_posting(p)
                if skills:
                    total_mentions += save_skill_mentions(conn, p["id"], skills)
            conn.commit()
        context.log.info(f"Extracted {total_mentions} skill mentions from {len(new_postings)} new postings.")
    else:
        context.log.info("No new postings detected; skill mentions up to date.")

    return MaterializeResult(
        value=total_mentions,
        metadata={
            "new_skill_mentions_extracted": MetadataValue.int(total_mentions),
        },
    )
