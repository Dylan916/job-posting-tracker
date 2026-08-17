"""Database initialization script to create tables and indexes."""

from pathlib import Path
from rich.console import Console
from db.connection import get_db_connection, close_pool

console = Console()


def init_db(drop_all: bool = False) -> None:
    """Read schema.sql and execute table creations."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        console.print(f"[bold red]Error:[/] {schema_path} not found.")
        return

    sql = schema_path.read_text(encoding="utf-8")

    console.print("[yellow]Connecting to PostgreSQL and running migrations...[/]")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if drop_all:
                    console.print("[red]Dropping existing tables...[/]")
                    cur.execute("""
                        DROP TABLE IF EXISTS skill_mentions CASCADE;
                        DROP TABLE IF EXISTS notifications_sent CASCADE;
                        DROP TABLE IF EXISTS subscriptions CASCADE;
                        DROP TABLE IF EXISTS users CASCADE;
                        DROP TABLE IF EXISTS postings CASCADE;
                    """)
                cur.execute(sql)
            conn.commit()
        console.print("[bold green]✓ Database initialized successfully with all tables and indexes.[/]")
    except Exception as e:
        console.print(f"[bold red]Database initialization failed:[/] {e}")
        raise
    finally:
        close_pool()


if __name__ == "__main__":
    import sys
    drop_flag = "--drop" in sys.argv
    init_db(drop_all=drop_flag)
