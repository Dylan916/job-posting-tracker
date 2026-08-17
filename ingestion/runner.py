"""Ingestion runner to execute pollers and perform idempotent database upserts."""

from typing import Any
import psycopg
from psycopg.types.json import Jsonb
from rich.console import Console
from rich.table import Table

from db.connection import get_db_connection
from ingestion.base import SourcePoller
from ingestion.greenhouse import GreenhousePoller
from ingestion.models import NormalizedPosting, IngestionStats
from ingestion.simplify import SimplifyPoller

console = Console()

DEFAULT_POLLERS: list[SourcePoller] = [
    SimplifyPoller(),
    GreenhousePoller(company_token="cloudflare", display_name="Cloudflare"),
    GreenhousePoller(company_token="datadog", display_name="Datadog"),
    GreenhousePoller(company_token="stripe", display_name="Stripe"),
]


def upsert_postings(
    conn: psycopg.Connection, postings: list[NormalizedPosting]
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Idempotently upsert postings into PostgreSQL.
    Returns: (list_of_new_postings, total_new_count, total_updated_count)
    """
    if not postings:
        return [], 0, 0

    query = """
        INSERT INTO postings (
            source, external_id, company, title, location, terms, is_remote, url, posted_at, raw_json, is_active, last_seen_at
        ) VALUES (
            %(source)s, %(external_id)s, %(company)s, %(title)s, %(location)s, %(terms)s, %(is_remote)s, %(url)s, %(posted_at)s, %(raw_json)s, %(is_active)s, NOW()
        )
        ON CONFLICT (source, external_id) DO UPDATE SET
            company = EXCLUDED.company,
            title = EXCLUDED.title,
            location = EXCLUDED.location,
            terms = EXCLUDED.terms,
            is_remote = EXCLUDED.is_remote,
            is_active = EXCLUDED.is_active,
            url = EXCLUDED.url,
            raw_json = EXCLUDED.raw_json,
            last_seen_at = NOW()
        RETURNING id, source, external_id, company, title, location, terms, is_remote, is_active, url, posted_at, (xmax = 0) AS is_new;
    """

    new_records: list[dict[str, Any]] = []
    new_count = 0
    updated_count = 0

    with conn.cursor() as cur:
        for p in postings:
            params = {
                "source": p.source,
                "external_id": p.external_id,
                "company": p.company,
                "title": p.title,
                "location": p.location,
                "terms": p.terms_display,
                "is_remote": p.is_remote,
                "is_active": p.is_active,
                "url": p.url,
                "posted_at": p.posted_at,
                "raw_json": Jsonb(p.raw_json),
            }
            cur.execute(query, params)
            row = cur.fetchone()
            if row:
                if row["is_new"] and row["is_active"]:
                    new_count += 1
                    new_records.append(row)
                else:
                    updated_count += 1

    conn.commit()
    return new_records, new_count, updated_count


def run_all_pollers(
    pollers: list[SourcePoller] | None = None,
) -> tuple[list[dict[str, Any]], list[IngestionStats]]:
    """Run all registered pollers and return newly discovered postings."""
    active_pollers = pollers or DEFAULT_POLLERS
    all_new_postings: list[dict[str, Any]] = []
    all_stats: list[IngestionStats] = []

    console.print(f"[bold cyan]Starting ingestion cycle across {len(active_pollers)} sources...[/]")

    with get_db_connection() as conn:
        for poller in active_pollers:
            console.print(f"[dim]Polling {poller.source_name}...[/]")
            postings, stats = poller.run()

            if postings:
                new_items, new_c, upd_c = upsert_postings(conn, postings)
                stats.new_postings = new_c
                stats.updated_postings = upd_c
                all_new_postings.extend(new_items)

            all_stats.append(stats)

    # Print summary table
    table = Table(title="Ingestion Execution Summary")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Fetched", justify="right")
    table.add_column("New Insertions", justify="right", style="green")
    table.add_column("Updated", justify="right", style="blue")
    table.add_column("Failures", justify="right", style="red")

    for s in all_stats:
        table.add_row(
            s.source,
            str(s.total_fetched),
            str(s.new_postings),
            str(s.updated_postings),
            str(s.failed_normalizations + len(s.errors)),
        )

    console.print(table)
    console.print(f"[bold green]Total new active postings detected:[/] {len(all_new_postings)}")
    return all_new_postings, all_stats


if __name__ == "__main__":
    run_all_pollers()
