"""Job postings querying and filtering endpoints."""

import math
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
import psycopg

from api.dependencies import get_db
from api.schemas import PaginatedPostings, PostingOut

router = APIRouter(prefix="/postings", tags=["Postings"])


@router.get("", response_model=PaginatedPostings)
def list_postings(
    company: str | None = Query(None, description="Filter by company name (case-insensitive)"),
    term: str | None = Query(None, description="Filter by recruiting season / term (e.g. 'Summer 2027', 'Fall 2026')"),
    keyword: str | None = Query(None, description="Search keyword across title, company, or description"),
    location: str | None = Query(None, description="Filter by location (e.g. 'San Francisco', 'Remote')"),
    is_remote: bool | None = Query(None, description="Filter by remote eligibility"),
    is_active: bool | None = Query(True, description="Filter by active status"),
    source: str | None = Query(None, description="Filter by data source (e.g. 'simplify_github', 'greenhouse_cloudflare')"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("first_seen_at", description="Field to sort by (first_seen_at, posted_at, company, title)"),
    sort_order: str = Query("desc", description="Sort direction (asc, desc)"),
    conn: psycopg.Connection = Depends(get_db),
) -> PaginatedPostings:
    """Retrieve paginated job and internship postings with dynamic filters."""
    conditions: list[str] = []
    params: list[Any] = []

    if company:
        conditions.append("company ILIKE %s")
        params.append(f"%{company.strip()}%")

    if term:
        conditions.append("(terms ILIKE %s OR title ILIKE %s)")
        params.extend([f"%{term.strip()}%", f"%{term.strip()}%"])

    if keyword:
        # Use full-text search vector for high performance keyword matching
        conditions.append("(search_vector @@ plainto_tsquery('english', %s) OR title ILIKE %s)")
        params.extend([keyword.strip(), f"%{keyword.strip()}%"])

    if location:
        conditions.append("location ILIKE %s")
        params.append(f"%{location.strip()}%")

    if is_remote is not None:
        conditions.append("is_remote = %s")
        params.append(is_remote)

    if is_active is not None:
        conditions.append("is_active = %s")
        params.append(is_active)

    if source:
        conditions.append("source = %s")
        params.append(source.strip())

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Validate sorting fields
    allowed_sorts = {"first_seen_at", "posted_at", "company", "title", "id"}
    safe_sort_by = sort_by if sort_by in allowed_sorts else "first_seen_at"
    safe_sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    offset = (page - 1) * page_size

    count_query = f"SELECT COUNT(*) AS total FROM postings {where_clause};"
    select_query = f"""
        SELECT 
            id, source, external_id, company, title, location, terms, 
            is_remote, url, posted_at, first_seen_at, last_seen_at, is_active
        FROM postings
        {where_clause}
        ORDER BY {safe_sort_by} {safe_sort_order} NULLS LAST
        LIMIT %s OFFSET %s;
    """

    with conn.cursor() as cur:
        # Get total matching rows
        cur.execute(count_query, params)
        total = cur.fetchone()["total"]

        # Fetch page slice
        cur.execute(select_query, params + [page_size, offset])
        rows = cur.fetchall()

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedPostings(
        items=[PostingOut(**r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{posting_id}", response_model=PostingOut)
def get_posting(posting_id: int, conn: psycopg.Connection = Depends(get_db)) -> PostingOut:
    """Retrieve details for a single job posting by ID."""
    query = """
        SELECT 
            id, source, external_id, company, title, location, terms, 
            is_remote, url, posted_at, first_seen_at, last_seen_at, is_active
        FROM postings
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (posting_id,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Posting ID {posting_id} not found")

    return PostingOut(**row)
