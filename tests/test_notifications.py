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


from unittest.mock import AsyncMock, patch
import pytest
from telegram.error import TelegramError
from notifications.dispatcher import dispatch_notifications_async, send_telegram_messages


@pytest.mark.asyncio
async def test_dispatch_notifications_calls_bot_send_message():
    """Test that dispatch_notifications_async fetches matched users and calls Telegram Bot API."""
    mock_postings = [
        {
            "id": 101,
            "company": "NVIDIA",
            "title": "Software Engineering Intern",
            "terms": "Summer 2027",
            "location": "Santa Clara, CA",
            "url": "https://nvidia.com/jobs/101",
            "source": "simplify_github",
        }
    ]

    with (
        patch("notifications.dispatcher.get_db_connection") as mock_get_db,
        patch("notifications.dispatcher.TELEGRAM_BOT_TOKEN", "mock_token"),
        patch("notifications.dispatcher.Bot") as MockBot,
        patch("notifications.dispatcher.match_postings_for_users") as mock_matcher,
        patch("notifications.dispatcher.record_notifications_sent") as mock_record,
    ):
        mock_matcher.return_value = {123456: mock_postings}
        mock_bot_instance = AsyncMock()
        MockBot.return_value = mock_bot_instance

        sent_count = await dispatch_notifications_async(mock_postings, mode="instant")

        assert sent_count == 1
        assert mock_bot_instance.send_message.called
        call_kwargs = mock_bot_instance.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 123456
        assert "NVIDIA" in call_kwargs["text"]
        assert "Software Engineering Intern" in call_kwargs["text"]
        assert mock_record.called


@pytest.mark.asyncio
async def test_send_telegram_messages_markdown_fallback():
    """Test that Telegram delivery falls back to sanitized text if markdown fails."""
    mock_bot = AsyncMock()
    # First call with markdown raises TelegramError, second call (fallback) succeeds
    mock_bot.send_message.side_effect = [TelegramError("Can't parse entities"), None]

    success = await send_telegram_messages(mock_bot, 123456, ["*Test Company* Role [Apply](http://test.com)"])

    assert success is True
    assert mock_bot.send_message.call_count == 2
