"""Unified Multi-ATS Poller for custom watched company boards (Greenhouse, Lever, Ashby)."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ingestion.base import SourcePoller
from ingestion.models import NormalizedPosting

logger = logging.getLogger(__name__)

TERM_PATTERN = re.compile(r"\b(Summer|Fall|Spring|Winter)\s*(202[5-9])\b", re.IGNORECASE)


class MultiATSPoller(SourcePoller):
    """Poller capable of fetching and normalizing job postings across Greenhouse, Lever, and Ashby."""

    def __init__(self, company_name: str, ats_provider: str, board_token: str) -> None:
        super().__init__()
        self.company_name = company_name.strip()
        self.ats_provider = ats_provider.lower().strip()
        self.board_token = board_token.strip()
        self.source_name = f"{self.ats_provider}_{self.board_token.lower()}"

    def poll(self) -> list[NormalizedPosting]:
        """Convenience method to run ingestion and return normalized records."""
        records, _ = self.run()
        return records

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw JSON job listings based on the ATS provider."""
        if self.ats_provider == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
            resp = self.fetch_with_retry(url)
            data = resp.json()
            jobs = data.get("jobs", [])
            return jobs if isinstance(jobs, list) else []

        elif self.ats_provider == "ashby":
            url = f"https://api.ashbyhq.com/posting-api/job-board/{self.board_token}"
            resp = self.fetch_with_retry(url)
            data = resp.json()
            jobs = data.get("jobs", [])
            return jobs if isinstance(jobs, list) else []

        elif self.ats_provider == "lever":
            url = f"https://api.lever.co/v0/postings/{self.board_token}?mode=json"
            resp = self.fetch_with_retry(url)
            data = resp.json()
            return data if isinstance(data, list) else []

        else:
            logger.warning(f"Unsupported ATS provider: {self.ats_provider}")
            return []

    def normalize(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        """Normalize job payload into a unified NormalizedPosting record."""
        if self.ats_provider == "greenhouse":
            return self._normalize_greenhouse(raw)
        elif self.ats_provider == "ashby":
            return self._normalize_ashby(raw)
        elif self.ats_provider == "lever":
            return self._normalize_lever(raw)
        return None

    def _normalize_greenhouse(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        job_id = str(raw.get("id") or raw.get("internal_job_id") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not job_id or not title:
            return None

        raw_location = raw.get("location", {})
        location_name = raw_location.get("name") if isinstance(raw_location, dict) else str(raw_location)
        is_remote = "remote" in (location_name or "").lower()

        terms = self._extract_terms(title)

        posted_at = None
        updated_at = raw.get("updated_at")
        if updated_at:
            try:
                posted_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_at = None

        return NormalizedPosting(
            source=self.source_name,
            external_id=job_id,
            company=self.company_name,
            title=title,
            location=location_name or None,
            terms=terms,
            is_remote=is_remote,
            url=raw.get("absolute_url"),
            posted_at=posted_at,
            raw_json=raw,
        )

    def _normalize_ashby(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        job_id = str(raw.get("id") or "").strip()
        title = str(raw.get("title") or "").strip()
        if not job_id or not title:
            return None

        location_name = raw.get("location") or raw.get("department") or None
        is_remote = bool(raw.get("isRemote") or "remote" in str(location_name or "").lower())

        terms = self._extract_terms(title)

        posted_at = None
        pub_at = raw.get("publishedAt")
        if pub_at:
            try:
                posted_at = datetime.fromisoformat(pub_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_at = None

        return NormalizedPosting(
            source=self.source_name,
            external_id=job_id,
            company=self.company_name,
            title=title,
            location=location_name,
            terms=terms,
            is_remote=is_remote,
            url=raw.get("jobUrl"),
            posted_at=posted_at,
            raw_json=raw,
        )

    def _normalize_lever(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        job_id = str(raw.get("id") or "").strip()
        title = str(raw.get("text") or "").strip()
        if not job_id or not title:
            return None

        categories = raw.get("categories", {})
        location_name = categories.get("location") if isinstance(categories, dict) else None
        is_remote = "remote" in str(location_name or "").lower() or raw.get("workplaceType") == "remote"

        terms = self._extract_terms(title)

        posted_at = None
        created_at_ms = raw.get("createdAt")
        if created_at_ms and isinstance(created_at_ms, (int, float)):
            try:
                posted_at = datetime.fromtimestamp(created_at_ms / 1000.0)
            except Exception:
                posted_at = None

        return NormalizedPosting(
            source=self.source_name,
            external_id=job_id,
            company=self.company_name,
            title=title,
            location=location_name,
            terms=terms,
            is_remote=is_remote,
            url=raw.get("hostedUrl"),
            posted_at=posted_at,
            raw_json=raw,
        )

    def _extract_terms(self, title: str) -> list[str]:
        terms: list[str] = []
        matches = TERM_PATTERN.findall(title)
        for season, year in matches:
            terms.append(f"{season.capitalize()} {year}")

        if not terms and ("intern" in title.lower() or "co-op" in title.lower()):
            terms.append("Internship")

        return terms


def load_all_watched_companies(conn) -> list[dict[str, str]]:
    """Load combined watched companies from config JSON and database."""
    companies_dict: dict[tuple[str, str], dict[str, str]] = {}

    # 1. Load config file
    config_path = Path(__file__).resolve().parent.parent / "config" / "watched_companies.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                items = json.load(f)
                for item in items:
                    key = (item["ats_provider"].lower(), item["board_token"].lower())
                    companies_dict[key] = item
        except Exception as e:
            logger.error(f"Error reading {config_path}: {e}")

    # 2. Load DB custom companies
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT company_name, ats_provider, board_token FROM watched_companies WHERE is_active = TRUE;")
            for r in cur.fetchall():
                key = (r["ats_provider"].lower(), r["board_token"].lower())
                companies_dict[key] = {
                    "company_name": r["company_name"],
                    "ats_provider": r["ats_provider"],
                    "board_token": r["board_token"],
                }
    except Exception as e:
        logger.error(f"Error fetching from watched_companies table: {e}")

    return list(companies_dict.values())
