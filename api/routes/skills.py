"""FastAPI endpoints for skill-demand analytics and hiring trends."""

from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import psycopg

from api.dependencies import get_db

router = APIRouter(prefix="/skills", tags=["Skill Analytics"])


class SkillCount(BaseModel):
    skill: str
    category: str
    count: int
    percentage_of_postings: float = Field(description="Percentage of total postings (e.g. 0.84 means 0.84%, less than 1%)")
    percentage_of_skills: float = Field(description="Share of this skill among all extracted skill mentions (e.g. 43.9%)")


class CategorySummary(BaseModel):
    category: str
    total_mentions: int
    skills: list[dict[str, Any]]


@router.get("/top", response_model=list[SkillCount])
def get_top_skills(
    term: str | None = Query(None, description="Filter by recruiting season (e.g. 'Summer 2027', 'Fall 2026')"),
    category: str | None = Query(None, description="Filter by skill category (e.g. 'Languages', 'Cloud & DevOps')"),
    limit: int = Query(15, ge=1, le=100, description="Max skills to return"),
    conn: psycopg.Connection = Depends(get_db),
) -> list[SkillCount]:
    """Retrieve top in-demand tech skills with percentage of postings and share of total skills."""
    conditions: list[str] = []
    params: list[Any] = []

    if term:
        conditions.append("(p.terms ILIKE %s OR p.title ILIKE %s)")
        params.extend([f"%{term.strip()}%", f"%{term.strip()}%"])

    if category:
        conditions.append("s.category ILIKE %s")
        params.append(f"%{category.strip()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    skills_query = f"""
        SELECT 
            s.skill, 
            s.category, 
            COUNT(s.id) AS count
        FROM skill_mentions s
        JOIN postings p ON s.posting_id = p.id
        {where_clause}
        GROUP BY s.skill, s.category
        ORDER BY count DESC
        LIMIT %s;
    """

    with conn.cursor() as cur:
        # Get total postings count
        if term:
            cur.execute("SELECT COUNT(*) AS total FROM postings WHERE terms ILIKE %s OR title ILIKE %s;", (f"%{term.strip()}%", f"%{term.strip()}%"))
        else:
            cur.execute("SELECT COUNT(*) AS total FROM postings;")
        total_postings_row = cur.fetchone()
        total_postings = total_postings_row["total"] if total_postings_row else 1
        if total_postings == 0:
            total_postings = 1

        # Get total skill mentions count in this filter
        total_skills_query = f"""
            SELECT COUNT(s.id) AS total_skills
            FROM skill_mentions s
            JOIN postings p ON s.posting_id = p.id
            {where_clause};
        """
        cur.execute(total_skills_query, params)
        total_skills_row = cur.fetchone()
        total_skills = total_skills_row["total_skills"] if total_skills_row else 1
        if total_skills == 0:
            total_skills = 1

        cur.execute(skills_query, params + [limit])
        rows = cur.fetchall()

    results: list[SkillCount] = []
    for r in rows:
        pct_postings = round((r["count"] / total_postings) * 100, 2)
        pct_skills = round((r["count"] / total_skills) * 100, 2)
        results.append(
            SkillCount(
                skill=r["skill"],
                category=r["category"] or "General",
                count=r["count"],
                percentage_of_postings=pct_postings,
                percentage_of_skills=pct_skills,
            )
        )

    return results


@router.get("/by-category", response_model=list[CategorySummary])
def get_skills_by_category(conn: psycopg.Connection = Depends(get_db)) -> list[CategorySummary]:
    """Retrieve skill breakdown grouped by category."""
    query = """
        SELECT 
            category,
            skill,
            COUNT(*) AS count
        FROM skill_mentions
        GROUP BY category, skill
        ORDER BY category ASC, count DESC;
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    categories_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        cat = r["category"] or "Other"
        if cat not in categories_map:
            categories_map[cat] = {
                "category": cat,
                "total_mentions": 0,
                "skills": [],
            }
        categories_map[cat]["total_mentions"] += r["count"]
        categories_map[cat]["skills"].append({
            "skill": r["skill"],
            "count": r["count"],
        })

    # Sort categories by total mentions descending
    sorted_categories = sorted(
        categories_map.values(), key=lambda c: c["total_mentions"], reverse=True
    )
    return [CategorySummary(**c) for c in sorted_categories]
