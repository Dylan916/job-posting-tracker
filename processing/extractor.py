"""Skill extraction engine with full ATS job description enrichment."""

import html
import re
from typing import Any
import httpx
import psycopg
from rich.console import Console
from rich.progress import track

from db.connection import get_db_connection
from processing.taxonomy import SKILL_TAXONOMY

console = Console()
CLEAN_HTML_REGEX = re.compile(r"<[^>]+>")


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and unescape HTML entities."""
    if not raw_html:
        return ""
    text = CLEAN_HTML_REGEX.sub(" ", raw_html)
    return html.unescape(text)


def extract_skills_from_text(text: str) -> list[tuple[str, str]]:
    """Scan arbitrary text and return list of matched (skill_name, category) tuples."""
    if not text:
        return []

    cleaned = clean_html(text)
    matched: list[tuple[str, str]] = []
    for skill_def in SKILL_TAXONOMY:
        if skill_def.pattern.search(cleaned):
            matched.append((skill_def.name, skill_def.category))

    return matched


def extract_skills_from_posting(posting: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract skills from title, description, and metadata fields."""
    title = str(posting.get("title") or "")
    raw_json = posting.get("raw_json") or {}
    
    text_corpus = [title]
    if isinstance(raw_json, dict):
        for key in ("content", "description", "requirements", "notes", "category", "degrees"):
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


def enrich_and_extract_greenhouse_descriptions(batch_size: int = 150) -> int:
    """Fetch full job descriptions from Greenhouse ATS API and extract detailed tech skills."""
    console.print("[bold cyan]Fetching full job descriptions from Greenhouse ATS APIs...[/]")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source, external_id, company, title 
                FROM postings 
                WHERE source LIKE 'greenhouse_%%' AND is_active = TRUE
                ORDER BY id ASC
                LIMIT %s;
            """, (batch_size,))
            greenhouse_postings = cur.fetchall()

    if not greenhouse_postings:
        console.print("[dim]No Greenhouse postings found for description enrichment.[/]")
        return 0

    client = httpx.Client(timeout=10.0, follow_redirects=True)
    total_skills = 0

    with get_db_connection() as conn:
        for p in track(greenhouse_postings, description="Enriching full job descriptions..."):
            company_token = p["source"].replace("greenhouse_", "")
            job_id = p["external_id"]
            url = f"https://boards-api.greenhouse.io/v1/boards/{company_token}/jobs/{job_id}"

            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", "")
                    skills = extract_skills_from_text(f"{p['title']} {content}")
                    if skills:
                        total_skills += save_skill_mentions(conn, p["id"], skills)
            except Exception:
                continue

        conn.commit()

    console.print(f"[bold green]✓ Enriched {len(greenhouse_postings)} full job descriptions and added {total_skills} skill mentions.[/]")
    return total_skills


def backfill_all_skills() -> int:
    """Extract skills from titles and metadata, plus enrich full ATS descriptions."""
    console.print("[bold cyan]Starting comprehensive skill extraction...[/]")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, raw_json FROM postings WHERE is_active = TRUE ORDER BY id ASC;")
            postings = cur.fetchall()

        total_mentions = 0
        console.print(f"Analyzing {len(postings)} active postings for tech skills...")

        with conn.cursor() as cur:
            for p in track(postings, description="Scanning postings..."):
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

    # Also enrich full descriptions for Greenhouse ATS postings
    enrich_mentions = enrich_and_extract_greenhouse_descriptions(batch_size=200)
    total_mentions += enrich_mentions

    console.print(f"[bold green]✓ Comprehensive skill extraction complete: {total_mentions} total skill mentions recorded.[/]")
    return total_mentions


if __name__ == "__main__":
    backfill_all_skills()
