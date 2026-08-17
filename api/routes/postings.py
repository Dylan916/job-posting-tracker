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
    keyword: str | None = Query(None, description="Search keyword in title, company, or search_vector"),
    location: str | None = Query(None, description="Filter by location string"),
    is_remote: bool | None = Query(None, description="Filter remote positions"),
    is_us_only: bool | None = Query(None, description="Filter exclusively for US-based positions"),
    is_undergrad_only: bool | None = Query(None, description="Filter out PhD, Masters, MBA, and graduate degree roles"),
    is_active: bool | None = Query(True, description="Filter active/open positions (default true)"),
    source: str | None = Query(None, description="Filter by data source (e.g. 'simplify_github', 'greenhouse_cloudflare')"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("posted_at", description="Field to sort by (posted_at, first_seen_at, company, title)"),
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

    if is_us_only is True:
        # Match US state codes, major tech hubs, country designations, or domestic remote
        us_regex = r"\y(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC|USA|United States|NYC|SF|San Francisco|New York|Seattle|Austin|Chicago|Boston|Los Angeles|Remote in USA|US Remote)\y"
        non_us_regex = r"\y(UK|Canada|London|Toronto|Vancouver|Waterloo|Montreal|Singapore|India|Australia|Sydney|Berlin|Germany|France|Paris|Dublin|Ireland|Zurich|Switzerland|Tokyo|Japan|Seoul|Korea)\y"
        conditions.append(f"(location ~* %s AND (location !~* %s OR location ~* '\\y(USA|United States|CA|NY|TX|WA|IL)\\y'))")
        params.extend([us_regex, non_us_regex])

    if is_undergrad_only is True or str(is_undergrad_only).lower() in ("true", "1"):
        # Exclude PhD, Masters, MBA, Postdoc from title AND from Simplify's structured 'degrees' JSON array
        grad_regex = r"(\y(PhD|Doctoral|Doctorate|Masters|MS|MBA|Postdoc|Post-Doc)\y|Ph\.D|Master'?s|Advanced Degree|(?<!under)graduate)"
        conditions.append("""
            (
                title !~* %s
                AND NOT (
                    raw_json->'degrees' IS NOT NULL 
                    AND (raw_json->'degrees' ? 'PhD' OR raw_json->'degrees' ? 'Master''s' OR raw_json->'degrees' ? 'MBA')
                    AND NOT (raw_json->'degrees' ? 'Bachelor''s')
                )
            )
        """)
        params.append(grad_regex)

    if is_active is not None:
        conditions.append("is_active = %s")
        params.append(is_active)

    if source:
        conditions.append("source = %s")
        params.append(source.strip())

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Validate sorting fields
    allowed_sorts = {"posted_at", "first_seen_at", "company", "title", "id"}
    safe_sort_by = sort_by if sort_by in allowed_sorts else "posted_at"
    safe_sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    offset = (page - 1) * page_size

    count_query = f"SELECT COUNT(*) AS total FROM postings {where_clause};"
    select_query = f"""
        SELECT 
            id, source, external_id, company, title, location, terms, 
            is_remote, url, posted_at, first_seen_at, last_seen_at, is_active
        FROM postings
        {where_clause}
        ORDER BY {safe_sort_by} {safe_sort_order} NULLS LAST, id DESC
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
