"""Tests for FastAPI Web Dashboard delivery and API endpoints."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.dependencies import get_db


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    return TestClient(app)


def test_homepage_delivery(client):
    """Test that the root URL '/' serves index.html with 200 OK and correct branding."""
    response = client.get("/")
    assert response.status_code == 200
    assert "InternIndex" in response.text
    assert "Summer 2027" in response.text


def test_static_assets_delivery(client):
    """Test that CSS and JS static files load with 200 OK and no 404s."""
    css_res = client.get("/css/style.css")
    assert css_res.status_code == 200
    assert "font-family" in css_res.text or "color" in css_res.text

    js_res = client.get("/js/app.js")
    assert js_res.status_code == 200
    assert "apiClient" in js_res.text or "loadPostings" in js_res.text


def test_openapi_swagger_docs(client):
    """Test that Swagger UI and OpenAPI schemas load with 200 OK."""
    docs_res = client.get("/docs")
    assert docs_res.status_code == 200

    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    spec = openapi_res.json()
    assert "/api/v1/postings" in spec["paths"]
    assert "/api/v1/health" in spec["paths"]


def test_postings_endpoint_with_mock_db(client):
    """Test /api/v1/postings with mocked database dependency."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"total": 1}
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "source": "simplify_github",
            "external_id": "test_1",
            "company": "Anthropic",
            "title": "AI Research Intern",
            "location": "San Francisco, CA",
            "terms": "Summer 2027",
            "is_remote": False,
            "url": "https://anthropic.com",
            "posted_at": now,
            "first_seen_at": now,
            "last_seen_at": now,
            "is_active": True,
        }
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    app.dependency_overrides[get_db] = lambda: mock_conn

    try:
        response = client.get("/api/v1/postings?term=Summer%202027&is_undergrad_only=true&is_us_only=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["company"] == "Anthropic"
        assert data["items"][0]["title"] == "AI Research Intern"
    finally:
        app.dependency_overrides.clear()
