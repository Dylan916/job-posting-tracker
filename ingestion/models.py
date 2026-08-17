"""Pydantic data models for job postings and ingestion results."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


class NormalizedPosting(BaseModel):
    """Normalized schema across all heterogeneous ATS and aggregator sources."""

    source: str
    external_id: str
    company: str
    title: str
    location: str | None = None
    terms: list[str] = Field(default_factory=list)
    is_remote: bool = False
    is_active: bool = True
    url: str | None = None
    posted_at: datetime | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "company", mode="before")
    @classmethod
    def clean_strings(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("is_remote", mode="before")
    @classmethod
    def determine_remote(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return "remote" in v.lower()
        return False

    @property
    def terms_display(self) -> str | None:
        """Comma-separated string of terms e.g. 'Summer 2027, Fall 2026'."""
        clean = [t.strip() for t in self.terms if t and t.strip() and t.strip().upper() != "N/A"]
        return ", ".join(clean) if clean else None


class IngestionStats(BaseModel):
    """Statistics for a single poller execution run."""

    source: str
    total_fetched: int = 0
    new_postings: int = 0
    updated_postings: int = 0
    failed_normalizations: int = 0
    errors: list[str] = Field(default_factory=list)
