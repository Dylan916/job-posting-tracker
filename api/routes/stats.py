"""Aggregated statistics and hiring trend endpoints."""

from fastapi import APIRouter, Depends
import psycopg

from api.dependencies import get_db
from api.schemas import CompanyBreakdown, SourceBreakdown, StatsResponse, TermBreakdown

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("", response_model=StatsResponse)
def get_stats(conn: psycopg.Connection = Depends(get_db)) -> StatsResponse:
    """Compute aggregate counts, source breakdown, and recruiting cycle distribution."""
    with conn.cursor() as cur:
        # Total and active metrics
        cur.execute("""
            SELECT 
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_active = TRUE) AS active,
                COUNT(*) FILTER (WHERE is_remote = TRUE) AS remote
            FROM postings;
        """)
        summary = cur.fetchone()
        total_postings = summary["total"] if summary else 0
        active_postings = summary["active"] if summary else 0
        remote_postings = summary["remote"] if summary else 0

        # Breakdown by Source
        cur.execute("""
            SELECT source, COUNT(*) AS count 
            FROM postings 
            GROUP BY source 
            ORDER BY count DESC;
        """)
        source_rows = cur.fetchall()

        # Top 15 Companies
        cur.execute("""
            SELECT company, COUNT(*) AS count 
            FROM postings 
            WHERE company IS NOT NULL AND company != ''
            GROUP BY company 
            ORDER BY count DESC 
            LIMIT 15;
        """)
        company_rows = cur.fetchall()

        # Breakdown by Season/Term
        # Extract terms by splitting comma-separated terms string
        cur.execute("""
            SELECT TRIM(term_item) AS term, COUNT(*) AS count
            FROM (
                SELECT unnest(string_to_array(terms, ', ')) AS term_item
                FROM postings
                WHERE terms IS NOT NULL AND terms != ''
            ) t
            WHERE TRIM(term_item) != '' AND UPPER(TRIM(term_item)) != 'N/A'
            GROUP BY TRIM(term_item)
            ORDER BY count DESC
            LIMIT 15;
        """)
        term_rows = cur.fetchall()

    return StatsResponse(
        total_postings=total_postings,
        active_postings=active_postings,
        remote_postings=remote_postings,
        by_source=[SourceBreakdown(source=r["source"], count=r["count"]) for r in source_rows],
        by_term=[TermBreakdown(term=r["term"], count=r["count"]) for r in term_rows],
        top_companies=[CompanyBreakdown(company=r["company"], count=r["count"]) for r in company_rows],
    )
