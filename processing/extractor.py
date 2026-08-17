"""Skill extraction engine using curated taxonomy regex patterns."""

import json
from typing import Any
import psycopg
from rich.console import Console
from rich.progress import track

from db.connection import get_db_connection
from processing.taxonomy import SKILL_TAXONOMY

console = Console()


def extract_skills_from_text(text: str) -> list[tuple[str, str]]:
    """Scan arbitrary text and return list of matched (skill_name, category) tuples."""
    if not text:
        return []

    matched: list[tuple[str, str]] = []
    for skill_def in SKILL_TAXONOMY:
        if skill_def.pattern.search(text):
            matched.append((skill_def.name, skill_def.category))

    return matched


def extract_skills_from_posting(posting: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract skills from a posting record (title + location + raw_json fields)."""
    title = str(posting.get("title") or "")
    raw_json = posting.get("raw_json") or {}
    
    # Compile all relevant textual fields
    text_corpus = [title]
    if isinstance(raw_json, dict):
        for key in ("category", "description", "requirements", "notes", "sponsorship", "degrees"):
            val = raw_json.get(key)
            if isinstance(val, list):
                text_corpus.extend(str(item) for item in val)
            elif isinstance(val, str):
                text_corpus.append(val)

    combined_text = " ".join(text_corpus)
    return extract_skills_from_text(combined_text)


def save_skill_mentions(
    conn: psycopg.Connection, posting_id: int, skills: list[tuple[str, str]]
) -> int:
    """Save extracted skills to skill_mentions table idempotently."""
    if not skills:
        return 0

    query = """
        INSERT INTO skill_mentions (posting_id, skill, category, extracted_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (posting_id, skill) DO NOTHING;
    """
    inserted = 0
    with conn.cursor() as cur:
        for skill_name, category in skills:
            cur.execute(query, (posting_id, skill_name, category))
            inserted += cur.rowcount
    return inserted


def backfill_all_skills(batch_size: int = 1000) -> int:
    """Extract and persist skills for all postings currently in PostgreSQL."""
    console.print("[bold cyan]Starting skill extraction across all job postings...[/]")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, raw_json FROM postings ORDER BY id ASC;")
            postings = cur.fetchall()

        total_postings = len(postings)
        total_mentions = 0

        console.print(f"Analyzing {total_postings} postings for tech skill mentions...")

        with conn.cursor() as cur:
            for p in track(postings, description="Extracting skills..."):
                skills = extract_skills_from_posting(p)
                if skills:
                    query = """
                        INSERT INTO skill_mentions (posting_id, skill, category, extracted_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (posting_id, skill) DO NOTHING;
                    """
                    for skill_name, category in skills:
                        cur.execute(query, (p["id"], skill_name, category))
                        total_mentions += 1

            conn.commit()

    console.print(f"[bold green]✓ Successfully extracted and recorded {total_mentions} skill mentions.[/]")
    return total_mentions


if __name__ == "__main__":
    backfill_all_skills()
