"""Poller for Greenhouse ATS JSON board endpoints with term extraction."""

import re
from datetime import datetime
from typing import Any

from ingestion.base import SourcePoller
from ingestion.models import NormalizedPosting

TERM_PATTERN = re.compile(r"\b(Summer|Fall|Spring|Winter)\s*(202[5-9])\b", re.IGNORECASE)


class GreenhousePoller(SourcePoller):
    """Poller that ingests job postings directly from Greenhouse ATS public APIs."""

    def __init__(self, company_token: str, display_name: str | None = None) -> None:
        super().__init__()
        self.company_token = company_token.lower().strip()
        self.display_name = display_name or company_token.capitalize()
        self.source_name = f"greenhouse_{self.company_token}"

    def fetch(self) -> list[dict[str, Any]]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.company_token}/jobs"
        response = self.fetch_with_retry(url)
        data = response.json()
        jobs = data.get("jobs", [])
        return jobs if isinstance(jobs, list) else []

    def normalize(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        job_id = str(raw.get("id") or raw.get("internal_job_id") or "").strip()
        title = str(raw.get("title") or "").strip()

        if not job_id or not title:
            return None

        # Location extraction
        raw_location = raw.get("location", {})
        location_name = raw_location.get("name") if isinstance(raw_location, dict) else str(raw_location)
        is_remote = "remote" in (location_name or "").lower()

        # Term extraction from title
        terms: list[str] = []
        matches = TERM_PATTERN.findall(title)
        for season, year in matches:
            terms.append(f"{season.capitalize()} {year}")

        if not terms and ("intern" in title.lower() or "co-op" in title.lower()):
            terms.append("Internship")

        # Parse ISO updated timestamp
        posted_at: datetime | None = None
        updated_at = raw.get("updated_at")
        if updated_at:
            try:
                posted_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_at = None

        url = raw.get("absolute_url")

        return NormalizedPosting(
            source=self.source_name,
            external_id=job_id,
            company=self.display_name,
            title=title,
            location=location_name or None,
            terms=terms,
            is_remote=is_remote,
            url=url,
            posted_at=posted_at,
            raw_json=raw,
        )
