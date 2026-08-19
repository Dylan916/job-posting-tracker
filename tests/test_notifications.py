"""Tests for subscription matching logic and Telegram message formatting."""

from notifications.dispatcher import format_batch_message, format_posting_item
from notifications.matcher import matches_subscription


def test_matcher_term_subscription():
    """Test that a term subscription matches only matching terms."""
    sub = {"term_filter": "Summer 2027", "company_filter": None, "keyword_filter": None, "location_filter": None}

    matching_posting = {"company": "Google", "title": "Software Intern", "terms": "Summer 2027", "location": "CA"}
    non_matching_posting = {"company": "Google", "title": "Software Intern", "terms": "Fall 2026", "location": "CA"}

    assert matches_subscription(matching_posting, sub) is True
    assert matches_subscription(non_matching_posting, sub) is False


def test_matcher_company_subscription():
    """Test that a company subscription matches specific companies case-insensitively."""
    sub = {"term_filter": None, "company_filter": "stripe", "keyword_filter": None, "location_filter": None}

    stripe_posting = {"company": "Stripe", "title": "Backend Intern", "terms": "Summer 2027", "location": "SF"}
    apple_posting = {"company": "Apple", "title": "iOS Intern", "terms": "Summer 2027", "location": "Cupertino"}

    assert matches_subscription(stripe_posting, sub) is True
    assert matches_subscription(apple_posting, sub) is False


def test_matcher_keyword_subscription():
    """Test that a keyword subscription matches role title keywords."""
    sub = {"term_filter": None, "company_filter": None, "keyword_filter": "Machine Learning", "location_filter": None}

    ml_posting = {"company": "Anthropic", "title": "Machine Learning Research Intern", "terms": "Summer 2027", "location": "SF"}
    fe_posting = {"company": "Figma", "title": "Frontend Engineer Intern", "terms": "Summer 2027", "location": "SF"}

    assert matches_subscription(ml_posting, sub) is True
    assert matches_subscription(fe_posting, sub) is False


def test_matcher_wildcard_all_subscription():
    """Test that an empty/unfiltered subscription matches everything."""
    sub = {"term_filter": None, "company_filter": None, "keyword_filter": None, "location_filter": None}

    any_posting = {"company": "Datadog", "title": "Site Reliability Intern", "terms": "Summer 2027", "location": "NYC"}

    assert matches_subscription(any_posting, sub) is True


def test_telegram_message_chunker_under_4096_chars():
    """Test that large batches of postings are chunked safely under Telegram's 4,096 character limit."""
    sample_postings = [
        {
            "company": f"Tech Company #{i}",
            "title": f"Senior Software Engineer Systems & Infrastructure Intern #{i}",
            "location": "San Francisco, CA, Seattle, WA, New York, NY, Austin, TX",
            "terms": "Summer 2027",
            "is_remote": True,
            "url": f"https://example.com/apply/{i}",
            "source": "simplify_github",
        }
        for i in range(1, 30)
    ]

    chunks = format_batch_message(sample_postings)

    assert len(chunks) > 1, "Expected large batch to be split into multiple chunks"
    for chunk in chunks:
        assert len(chunk) <= 4096, f"Chunk exceeded 4,096 characters (was {len(chunk)})"
        assert "Tech Company" in chunk
