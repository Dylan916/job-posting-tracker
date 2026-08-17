"""Database connection pool management."""

import os
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/job_tracker")

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Retrieve or initialize the global connection pool."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            open=True,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
    return _pool


def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.close()
        _pool = None


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Context manager for acquiring a database connection from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
