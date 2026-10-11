"""Tests for Instagram URL canonicalization, requisition extraction, and metadata parsing."""

import pytest
from processing.instagram_extractor import (
    canonicalize_url,
    extract_requisition_id,
    extract_terms_from_text,
    split_company_and_title,
)


def test_canonicalize_url_strips_utm_and_igshid():
    raw_url = "https://careers.rivian.com/jobs/12345?utm_source=instagram&utm_medium=story&igshid=abc123xyz"
    expected = "https://careers.rivian.com/jobs/12345"
    assert canonicalize_url(raw_url) == expected


def test_canonicalize_url_unwraps_instagram_redirect():
    raw_redirect = "https://l.instagram.com/?u=https%3A%2F%2Fboards.greenhouse.io%2Fdatadog%2Fjobs%2F5581920%3Futm_source%3Dstory"
    expected = "https://boards.greenhouse.io/datadog/jobs/5581920"
    assert canonicalize_url(raw_redirect) == expected


def test_extract_requisition_id():
    # Greenhouse
    assert extract_requisition_id("https://boards.greenhouse.io/datadog/jobs/5581920") == "5581920"
    # Lever UUID
    assert extract_requisition_id("https://jobs.lever.co/company/12345678-1234-1234-1234-123456789abc") == "12345678-1234-1234-1234-123456789abc"
    # Workday style
    assert extract_requisition_id("https://company.wd1.myworkdayjobs.com/job/Palo-Alto/Software-Engineer_JR-10294") == "Software-Engineer_JR-10294"
    # None for root URL
    assert extract_requisition_id("https://careers.rivian.com/") is None


def test_extract_terms():
    assert extract_terms_from_text("Artificial Intelligence, Machine Learning - Summer 2027 Internships") == ["Summer 2027"]
    assert extract_terms_from_text("Software Engineer (Fall 2026)") == ["Fall 2026"]
    assert extract_terms_from_text("Senior Software Engineer") == []


def test_split_company_and_title():
    company, title = split_company_and_title("Software Engineer Intern - Rivian")
    assert company == "Rivian"
    assert title == "Software Engineer Intern"

    company2, title2 = split_company_and_title("Datadog Careers | Software Engineer Intern")
    assert company2 == "Datadog"
    assert title2 == "Software Engineer Intern"


def test_extract_from_webpage_schema_org(monkeypatch):
    import httpx
    from processing.instagram_extractor import extract_from_webpage

    html_content = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Artificial Intelligence & ML Intern - Summer 2027",
          "hiringOrganization": {"name": "Rivian"},
          "jobLocation": {"address": {"addressLocality": "Palo Alto"}}
        }
        </script>
      </head>
    </html>
    """

    class MockResponse:
        status_code = 200
        text = html_content
        url = "https://careers.rivian.com/jobs/55123"

    class MockClient:
        def get(self, url, **kwargs):
            return MockResponse()

    result = extract_from_webpage("https://careers.rivian.com/jobs/55123", client=MockClient())
    assert result is not None
    assert result["company"] == "Rivian"
    assert "Artificial Intelligence" in result["title"]
    assert result["location"] == "Palo Alto"
    assert result["terms"] == ["Summer 2027"]
    assert result["degrees"] == ["Bachelor's"]
    assert result["requisition_id"] == "55123"
    assert result["method"] == "schema_org"


def test_extract_from_webpage_masters_graduate_role():
    """Verify that graduate/masters roles like Faire are detected with Master's degree and location."""
    from processing.instagram_extractor import extract_from_webpage

    html_content = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Applied AI/ML Scientist, Intern",
          "hiringOrganization": {"name": "Faire"},
          "jobLocation": {"address": {"addressLocality": "San Francisco, CA"}},
          "description": "Qualifications: Must be currently pursuing an MS/Master's or PhD degree in Computer Science."
        }
        </script>
      </head>
    </html>
    """

    class MockResponse:
        status_code = 200
        text = html_content
        url = "https://job-boards.greenhouse.io/faire/jobs/612345"

    class MockClient:
        def get(self, url, **kwargs):
            return MockResponse()

    result = extract_from_webpage("https://job-boards.greenhouse.io/faire/jobs/612345", client=MockClient())
    assert result is not None
    assert result["company"] == "Faire"
    assert result["title"] == "Applied AI/ML Scientist, Intern"
    assert result["location"] == "San Francisco, CA"
    assert "Master's" in result["degrees"]
    assert "Bachelor's" not in result["degrees"]  # Undergrad filter will properly exclude this!


def test_extract_degrees_from_text():
    from processing.instagram_extractor import extract_degrees_from_text

    # Masters / Graduate role
    grad_text = "Applied AI/ML Scientist Intern. Currently enrolled in a Master's or MS degree program."
    degrees = extract_degrees_from_text(grad_text)
    assert "Master's" in degrees
    assert "Bachelor's" not in degrees

    # Undergrad role
    undergrad_text = "Software Engineer Intern. Currently pursuing a Bachelor's degree (BS) in Computer Science."
    assert extract_degrees_from_text(undergrad_text) == ["Bachelor's"]


def test_live_webpage_extraction_dynamic_greenhouse():
    """
    Dynamic live integration test:
    Queries Cloudflare's public board for whichever job is currently active,
    so this test NEVER goes stale or breaks when a specific requisition closes.
    """
    import httpx
    from processing.instagram_extractor import extract_from_webpage

    try:
        resp = httpx.get("https://boards-api.greenhouse.io/v1/boards/cloudflare/jobs", timeout=10.0)
        jobs = resp.json().get("jobs", [])
    except Exception:
        pytest.skip("External network unavailable")

    if not jobs:
        pytest.skip("No active jobs currently on board")

    # Pick the first currently open job on the live board
    live_url = jobs[0]["absolute_url"]
    result = extract_from_webpage(live_url)

    assert result is not None
    assert result["company"] == "Cloudflare"
    assert result["title"] != ""
    assert result["requisition_id"] is not None
    assert "degrees" in result
    assert isinstance(result["degrees"], list)




