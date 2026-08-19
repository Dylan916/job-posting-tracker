"""Tests for multi-source ingestion, ETag caching, and normalizers."""

import re
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from ingestion.ats_watcher import MultiATSPoller
from ingestion.models import NormalizedPosting
from ingestion.simplify import SimplifyPoller


def test_simplify_etag_304_not_modified(tmp_path):
    """Test that HTTP 304 returns an empty list without raising exceptions."""
    etag_file = tmp_path / ".test_etag.txt"
    etag_file.write_text("W/\"commit_hash_123\"", encoding="utf-8")

    poller = SimplifyPoller(etag_file=etag_file)

    mock_response = MagicMock()
    mock_response.status_code = 304

    with patch.object(poller, "fetch_with_retry", return_value=mock_response):
        result = poller.fetch()
        assert result == []


def test_simplify_normalize_valid_record(tmp_path):
    """Test normalizer extracts all fields into NormalizedPosting correctly."""
    poller = SimplifyPoller(etag_file=tmp_path / ".etag.txt")

    raw_record = {
        "id": "job_123",
        "company_name": "Stripe",
        "title": "Software Engineer Intern",
        "locations": ["San Francisco, CA", "Seattle, WA"],
        "terms": ["Summer 2027"],
        "active": True,
        "is_visible": True,
        "url": "https://stripe.com/jobs/123",
        "date_posted": 1786960000,
        "degrees": ["Bachelor's"],
    }

    normalized = poller.normalize(raw_record)

    assert normalized is not None
    assert normalized.company == "Stripe"
    assert normalized.title == "Software Engineer Intern"
    assert normalized.terms == ["Summer 2027"]
    assert normalized.location == "San Francisco, CA, Seattle, WA"
    assert normalized.is_remote is False
    assert normalized.is_active is True
    assert normalized.url == "https://stripe.com/jobs/123"
    assert normalized.source == "simplify_github"


def test_smart_summer_term_promotion(tmp_path):
    """Test that fresh summer postings (July/August 2026+) get promoted to Summer 2027 while preserving co-ops."""
    poller = SimplifyPoller(etag_file=tmp_path / ".etag.txt")

    # Case 1: Fresh summer role posted in August 2026 tagged Summer 2026 (e.g. Grainger / Tesla) -> Promote to 2027
    raw_summer = {
        "id": "summer_job",
        "company_name": "Tesla",
        "title": "AI Intern",
        "terms": ["Summer 2026"],
        "date_posted": 1786960000,  # August 2026
        "active": True,
    }
    norm_summer = poller.normalize(raw_summer)
    assert norm_summer is not None
    assert norm_summer.terms == ["Summer 2027"]

    # Case 2: Fall 2026 Co-op -> Strictly preserve Fall 2026
    raw_fall = {
        "id": "fall_job",
        "company_name": "Palo Alto Networks",
        "title": "Fall Co-op",
        "terms": ["Fall 2026"],
        "date_posted": 1786960000,
        "active": True,
    }
    norm_fall = poller.normalize(raw_fall)
    assert norm_fall is not None
    assert norm_fall.terms == ["Fall 2026"]

    # Case 3: Spring 2027 Co-op -> Strictly preserve Spring 2027
    raw_spring = {
        "id": "spring_job",
        "company_name": "AMD",
        "title": "Spring Co-op",
        "terms": ["Spring 2027"],
        "date_posted": 1786960000,
        "active": True,
    }
    norm_spring = poller.normalize(raw_spring)
    assert norm_spring is not None
    assert norm_spring.terms == ["Spring 2027"]


def test_ats_term_regex_extraction():
    """Test regex term extraction across Greenhouse, Ashby, and Lever title formats."""
    ats_term_pattern = re.compile(r"\b(Summer|Fall|Spring|Winter)\s*(202[5-9])\b", re.IGNORECASE)

    test_titles = [
        ("Software Engineer Intern (Summer 2027)", "Summer 2027"),
        ("Data Science Intern - Fall 2026", "Fall 2026"),
        ("Systems Co-op: Winter 2027", "Winter 2027"),
        ("Campus Quantitative Researcher - Spring 2027", "Spring 2027"),
    ]

    for title, expected_term in test_titles:
        match = ats_term_pattern.search(title)
        assert match is not None
        matched_term = f"{match.group(1).capitalize()} {match.group(2)}"
        assert matched_term == expected_term
