"""Unit tests for InstagramStoryPoller and story ingestion."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from ingestion.instagram import InstagramStoryPoller
from ingestion.models import NormalizedPosting


def test_instagram_poller_initialization():
    poller = InstagramStoryPoller(target_accounts=["@zero2sudo", "other_creator"])
    assert poller.target_accounts == ["zero2sudo", "other_creator"]
    assert poller.source_name == "instagram_stories"


def test_fetch_skips_stories_without_links():
    poller = InstagramStoryPoller(target_accounts=["zero2sudo"])
    poller.cl = MagicMock()
    poller.cl.user_id_from_username.return_value = "123456"

    # Story 1: Tip / advice without link sticker
    story_no_link = MagicMock()
    story_no_link.pk = 101
    story_no_link.story_link_stickers = []

    # Story 2: Job posting with link sticker
    story_with_link = MagicMock()
    story_with_link.pk = 102
    story_with_link.thumbnail_url = "https://example.com/thumb.jpg"
    story_with_link.taken_at = 1728670800
    story_with_link.caption_text = "New Rivian Internship"

    link_sticker = MagicMock()
    link_sticker.story_link.url = "https://careers.rivian.com/jobs/55123?utm_source=ig"
    story_with_link.story_link_stickers = [link_sticker]

    poller.cl.user_stories.return_value = [story_no_link, story_with_link]

    items = poller.fetch()
    assert len(items) == 1
    assert items[0]["story_id"] == "102"
    assert items[0]["canonical_url"] == "https://careers.rivian.com/jobs/55123"
    assert items[0]["requisition_id"] == "55123"


def test_normalize_valid_job_story():
    poller = InstagramStoryPoller(target_accounts=["zero2sudo"])

    raw = {
        "story_id": "102",
        "username": "zero2sudo",
        "raw_url": "https://careers.rivian.com/jobs/55123",
        "canonical_url": "https://careers.rivian.com/jobs/55123",
        "requisition_id": "55123",
        "image_url": "https://example.com/thumb.jpg",
        "posted_at": datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc),
    }

    with patch("ingestion.instagram.extract_job_posting_details") as mock_extract:
        mock_extract.return_value = {
            "company": "Rivian",
            "title": "Artificial Intelligence & ML Intern",
            "location": "Palo Alto, CA",
            "terms": ["Summer 2027"],
            "is_remote": False,
            "url": "https://careers.rivian.com/jobs/55123",
            "requisition_id": "55123",
            "method": "schema_org",
        }

        posting = poller.normalize(raw)
        assert posting is not None
        assert isinstance(posting, NormalizedPosting)
        assert posting.source == "instagram_zero2sudo"
        assert posting.company == "Rivian"
        assert posting.title == "Artificial Intelligence & ML Intern"
        assert posting.terms == ["Summer 2027"]
        assert posting.terms_display == "Summer 2027"


def test_normalize_skips_non_job_content():
    poller = InstagramStoryPoller(target_accounts=["zero2sudo"])

    raw = {
        "story_id": "103",
        "username": "zero2sudo",
        "raw_url": "https://youtube.com/watch?v=interview_tips",
        "canonical_url": "https://youtube.com/watch?v=interview_tips",
        "image_url": None,
        "posted_at": datetime.now(timezone.utc),
    }

    with patch("ingestion.instagram.extract_job_posting_details") as mock_extract:
        mock_extract.return_value = {
            "is_job_posting": False,
        }

        posting = poller.normalize(raw)
        assert posting is None
