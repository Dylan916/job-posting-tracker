"""Poller for SimplifyJobs GitHub repository listings with active status filtering."""

import os
from datetime import datetime, timezone
from typing import Any

from ingestion.base import SourcePoller
from ingestion.models import NormalizedPosting


class SimplifyPoller(SourcePoller):
    """Poller that ingests structured internship listings from SimplifyJobs GitHub repositories."""

    source_name: str = "simplify_github"

    def __init__(self, target_url: str | None = None) -> None:
        super().__init__()
        self.target_url = target_url or os.getenv(
            "SIMPLIFY_GITHUB_URL",
            "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
        )

    def fetch(self) -> list[dict[str, Any]]:
        response = self.fetch_with_retry(self.target_url)
        data = response.json()
        if isinstance(data, list):
            return data
        return []

    def normalize(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        raw_id = str(raw.get("id") or "").strip()
        company = str(raw.get("company_name") or raw.get("company") or "").strip()
        title = str(raw.get("title") or "").strip()

        if not company or not title:
            return None

        # Check whether the posting is actively open and visible
        is_active = bool(raw.get("active", True) and raw.get("is_visible", True))

        # Determine locations and remote status
        raw_locations = raw.get("locations") or []
        if isinstance(raw_locations, list):
            location_str = ", ".join(str(loc) for loc in raw_locations if loc)
        else:
            location_str = str(raw_locations)

        is_remote = "remote" in location_str.lower()

        # Extract terms (e.g. ['Summer 2027', 'Fall 2026'])
        raw_terms = raw.get("terms") or []
        terms = [str(t).strip() for t in raw_terms if str(t).strip() and str(t).strip().upper() != "N/A"]

        # Parse posted timestamp
        posted_at: datetime | None = None
        ts = raw.get("date_posted") or raw.get("date_updated")
        if ts:
            try:
                posted_at = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                posted_at = None

        url = raw.get("url") or raw.get("company_url")

        # Fallback external_id if missing
        external_id = raw_id if raw_id else f"{company}_{title}_{location_str}"

        return NormalizedPosting(
            source=self.source_name,
            external_id=external_id,
            company=company,
            title=title,
            location=location_str or None,
            terms=terms,
            is_remote=is_remote,
            is_active=is_active,
            url=url,
            posted_at=posted_at,
            raw_json=raw,
        )
