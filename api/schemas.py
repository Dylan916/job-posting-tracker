"""Pydantic schemas for FastAPI request and response validation."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class PostingOut(BaseModel):
    """Schema for returning a single job posting."""

    id: int
    source: str
    external_id: str
    company: str
    title: str
    location: str | None = None
    terms: str | None = None
    is_remote: bool = False
    url: str | None = None
    posted_at: datetime | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool


class PaginatedPostings(BaseModel):
    """Paginated response containing a list of postings and metadata."""

    items: list[PostingOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class SourceBreakdown(BaseModel):
    """Posting counts grouped by source."""

    source: str
    count: int


class TermBreakdown(BaseModel):
    """Posting counts grouped by recruiting term/season."""

    term: str
    count: int


class CompanyBreakdown(BaseModel):
    """Posting counts grouped by hiring company."""

    company: str
    count: int


class StatsResponse(BaseModel):
    """Aggregate statistics for job postings and recruiting seasons."""

    total_postings: int
    active_postings: int
    remote_postings: int
    by_source: list[SourceBreakdown]
    by_term: list[TermBreakdown]
    top_companies: list[CompanyBreakdown]


class HealthResponse(BaseModel):
    """Healthcheck endpoint response."""

    status: str = "ok"
    database_connected: bool
    total_postings: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
