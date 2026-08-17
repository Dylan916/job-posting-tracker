"""Abstract base class for all job posting source pollers."""

import time
from abc import ABC, abstractmethod
from typing import Any
import httpx
from rich.console import Console

from ingestion.models import NormalizedPosting, IngestionStats

console = Console()


class SourcePoller(ABC):
    """Base poller interface with built-in HTTP resilience, retries, and error isolation."""

    source_name: str = "base"
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "JobPostingTracker/1.0 (Summer Internship Bot)"},
            follow_redirects=True,
        )

    def fetch_with_retry(
        self, url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        """Fetch an HTTP endpoint with exponential backoff on rate limits and 5xx errors."""
        delay = self.retry_delay_seconds
        last_exception: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get(url, headers=headers, params=params)
                # Retry on 429 (Rate Limit) or 5xx server errors
                if response.status_code in (429, 500, 502, 503, 504):
                    console.print(
                        f"[yellow]Source {self.source_name}: HTTP {response.status_code} on attempt {attempt}/{self.max_retries}. Backing off {delay:.1f}s...[/]"
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Return directly on 304 (Not Modified) or 2xx
                if response.status_code == 304:
                    return response

                response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_exception = exc
                console.print(
                    f"[yellow]Source {self.source_name}: Network error ({exc}) on attempt {attempt}/{self.max_retries}. Retrying in {delay:.1f}s...[/]"
                )
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(
            f"Failed to fetch from {url} after {self.max_retries} attempts"
        ) from last_exception

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw listings from the source."""
        pass

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> NormalizedPosting | None:
        """Convert a single raw source dict to a NormalizedPosting instance."""
        pass

    def run(self) -> tuple[list[NormalizedPosting], IngestionStats]:
        """Fetch and normalize all postings from this source with dead-letter fault isolation."""
        stats = IngestionStats(source=self.source_name)
        normalized_records: list[NormalizedPosting] = []

        try:
            raw_records = self.fetch()
            stats.total_fetched = len(raw_records)
        except Exception as e:
            stats.errors.append(f"Fetch failed: {str(e)}")
            console.print(f"[bold red]Poller {self.source_name} fetch error:[/] {e}")
            return [], stats

        for raw in raw_records:
            try:
                posting = self.normalize(raw)
                if posting:
                    normalized_records.append(posting)
                else:
                    stats.failed_normalizations += 1
            except Exception as e:
                stats.failed_normalizations += 1
                stats.errors.append(f"Normalization failed for raw ID {raw.get('id', 'unknown')}: {e}")

        return normalized_records, stats
