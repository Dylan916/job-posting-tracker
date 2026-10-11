"""Poller for Instagram Stories to detect job link stickers and postings.

Monitors target creator accounts (e.g. @zero2sudo), extracts interactive link
stickers, filters out non-job content, and standardizes postings for ingestion.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from instagrapi import Client
from rich.console import Console

from db.connection import get_db_connection
from ingestion.base import SourcePoller
from ingestion.models import NormalizedPosting
from processing.instagram_extractor import (
    canonicalize_url,
    extract_job_posting_details,
    extract_requisition_id,
)
from processing.location_cleaner import normalize_location

console = Console()



class InstagramStoryPoller(SourcePoller):
    """Ingests job postings shared via Instagram Stories by tech creators."""

    source_name: str = "instagram_stories"

    def __init__(
        self,
        target_accounts: list[str] | None = None,
        session_path: str | None = None,
    ) -> None:
        super().__init__()
        targets = target_accounts or os.getenv("IG_TARGET_ACCOUNTS", "zero2sudo").split(",")
        self.target_accounts = [t.strip().lstrip("@") for t in targets if t.strip()]
        self.session_path = Path(session_path or os.getenv("IG_SESSION_PATH", "data/ig_session.json"))
        self.cl: Client | None = None

    def _init_client(self) -> Client | None:
        """Initialize and authenticate instagrapi client from cached session file."""
        if self.cl is not None:
            return self.cl

        if not self.session_path.exists():
            console.print(
                f"[yellow]Instagram session file not found at {self.session_path}. "
                "Run `python scripts/ig_login.py` to authenticate first.[/]"
            )
            return None

        try:
            cl = Client()
            cl.load_settings(self.session_path)
            self.cl = cl
            return self.cl
        except Exception as exc:
            console.print(f"[bold red]Failed to load Instagram session:[/] {exc}")
            return None

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch active 24-hour stories for all target creator accounts, skipping already-ingested story IDs."""
        cl = self._init_client()
        if not cl:
            return []

        # 1. Query database for story IDs we've already processed in the last 48 hours
        seen_story_ids: set[str] = set()
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT external_id FROM postings WHERE source LIKE 'instagram_%' AND first_seen_at >= NOW() - INTERVAL '48 hours';"
                    )
                    seen_story_ids = {str(row["external_id"]) for row in cur.fetchall()}
        except Exception as exc:
            console.print(f"[dim yellow]Could not query seen story IDs from database: {exc}[/]")

        story_items: list[dict[str, Any]] = []
        known_active_ids: list[str] = []

        for username in self.target_accounts:
            try:
                console.print(f"[dim]Checking Instagram stories for @{username}...[/]")
                user_id = cl.user_id_from_username(username)
                stories = cl.user_stories(user_id)

                for story in stories:
                    story_id = str(story.pk)

                    # If this exact story slide was already ingested, skip re-extracting it!
                    if story_id in seen_story_ids:
                        known_active_ids.append(story_id)
                        continue

                    target_url = None

                    # Check story.links (instagrapi 3.0+)
                    links = getattr(story, "links", []) or []
                    for link in links:
                        uri = getattr(link, "webUri", None) or getattr(link, "url", None)
                        if uri:
                            target_url = str(uri)
                            break

                    # Check story.stickers (instagrapi 3.0+)
                    if not target_url:
                        stickers = getattr(story, "stickers", []) or []
                        for st in stickers:
                            st_link = getattr(st, "story_link", None)
                            if st_link and getattr(st_link, "url", None):
                                target_url = str(st_link.url)
                                break

                    # Check legacy story_link_stickers (instagrapi 2.x)
                    if not target_url:
                        legacy_stickers = getattr(story, "story_link_stickers", []) or []
                        if legacy_stickers:
                            st_link = getattr(legacy_stickers[0], "story_link", None)
                            if st_link and getattr(st_link, "url", None):
                                target_url = str(st_link.url)

                    if not target_url:
                        continue

                    # Get story thumbnail image URL for vision fallback
                    thumbnail_url = getattr(story, "thumbnail_url", None)
                    if not thumbnail_url and getattr(story, "image_versions2", None):
                        candidates = story.image_versions2.get("candidates", [])
                        if candidates:
                            thumbnail_url = candidates[0].get("url")
                    if thumbnail_url:
                        thumbnail_url = str(thumbnail_url)

                    # Convert Unix timestamp or datetime
                    taken_at = getattr(story, "taken_at", None)
                    if isinstance(taken_at, (int, float)):
                        posted_at = datetime.fromtimestamp(taken_at, tz=timezone.utc)
                    elif isinstance(taken_at, datetime):
                        posted_at = taken_at
                    else:
                        posted_at = datetime.now(timezone.utc)

                    story_items.append({
                        "story_id": story_id,
                        "username": username,
                        "raw_url": target_url,
                        "canonical_url": canonicalize_url(target_url),
                        "requisition_id": extract_requisition_id(target_url),
                        "image_url": thumbnail_url,
                        "posted_at": posted_at,
                        "caption": getattr(story, "caption_text", "") or "",
                    })

            except Exception as exc:
                console.print(f"[bold red]Error fetching stories for @{username}:[/] {exc}")

        # Fast bulk-refresh last_seen_at for already-known stories in 1 query
        if known_active_ids:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE postings SET last_seen_at = NOW() WHERE source LIKE 'instagram_%' AND external_id = ANY(%s);",
                            (known_active_ids,),
                        )
                console.print(
                    f"[dim green]✓ {len(known_active_ids)} existing Instagram story postings refreshed in DB (skipped redundant extraction).[/]"
                )
            except Exception:
                pass

        return story_items


    def normalize(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        """
        Extract job metadata using two-tier parser (HTML -> Gemini Vision)
        and construct NormalizedPosting instance.
        """
        raw_url = raw.get("raw_url", "")
        image_url = raw.get("image_url")

        # Two-tier extraction
        details = extract_job_posting_details(url=raw_url, image_url=image_url)

        # Skip if classified as non-job content (interview advice, meme, etc.)
        if details.get("is_job_posting") is False:
            console.print(f"[dim]Story {raw['story_id']} is not a job opening. Skipping.[/]")
            return None

        company = details.get("company", "").strip() or "Unknown Company"
        title = details.get("title", "").strip() or "Job Opportunity"

        if company == "Unknown Company" and title == "Job Opportunity":
            return None

        # Build NormalizedPosting
        return NormalizedPosting(
            source=f"instagram_{raw['username']}",
            external_id=raw["story_id"],
            company=company,
            title=title,
            location=normalize_location(details.get("location")),
            terms=details.get("terms", []),
            is_remote=details.get("is_remote", False),
            is_active=True,
            url=details.get("url") or raw.get("canonical_url"),
            posted_at=raw.get("posted_at"),
            raw_json={
                "story_id": raw["story_id"],
                "creator": raw["username"],
                "degrees": details.get("degrees", ["Bachelor's"]),
                "requisition_id": details.get("requisition_id") or raw.get("requisition_id"),
                "extraction_method": details.get("method"),
                "original_url": raw_url,
                "image_url": image_url,
            },
        )

