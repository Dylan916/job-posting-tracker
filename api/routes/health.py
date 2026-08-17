"""Health and readiness check endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
import psycopg

from api.dependencies import get_db
from api.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
def healthcheck(conn: psycopg.Connection = Depends(get_db)) -> HealthResponse:
    """Check API and PostgreSQL database health."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM postings;")
            row = cur.fetchone()
            total_count = row["count"] if row else 0

        return HealthResponse(
            status="ok",
            database_connected=True,
            total_postings=total_count,
            timestamp=datetime.now(timezone.utc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection error: {exc}",
        ) from exc
