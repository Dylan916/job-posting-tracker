"""FastAPI dependency injection for database connections."""

from typing import Generator
import psycopg
from db.connection import get_pool


def get_db() -> Generator[psycopg.Connection, None, None]:
    """Dependency that provides a pooled database connection per request."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
