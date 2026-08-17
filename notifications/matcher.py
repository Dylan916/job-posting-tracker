"""Subscription matching logic to find users interested in new postings."""

from typing import Any
import psycopg
from rich.console import Console

console = Console()


def get_active_subscribers_with_subscriptions(conn: psycopg.Connection, mode: str = "instant") -> list[dict[str, Any]]:
    """Retrieve users whose notification_mode matches, along with their active subscriptions."""
    query = """
        SELECT 
            u.id AS user_id,
            u.telegram_chat_id,
            u.notification_mode,
            s.id AS subscription_id,
            s.company_filter,
            s.keyword_filter,
            s.location_filter,
            s.term_filter
        FROM users u
        LEFT JOIN subscriptions s ON u.id = s.user_id
        WHERE u.notification_mode = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (mode,))
        rows = cur.fetchall()

    # Group subscriptions by user
    users_map: dict[int, dict[str, Any]] = {}
    for r in rows:
        uid = r["user_id"]
        if uid not in users_map:
            users_map[uid] = {
                "user_id": uid,
                "telegram_chat_id": r["telegram_chat_id"],
                "notification_mode": r["notification_mode"],
                "subscriptions": [],
            }
        if r["subscription_id"] is not None:
            users_map[uid]["subscriptions"].append({
                "id": r["subscription_id"],
                "company_filter": r["company_filter"],
                "keyword_filter": r["keyword_filter"],
                "location_filter": r["location_filter"],
                "term_filter": r["term_filter"],
            })

    return list(users_map.values())


def matches_subscription(posting: dict[str, Any], sub: dict[str, Any]) -> bool:
    """Check if a posting satisfies a user's subscription filter criteria."""
    company_filter = (sub.get("company_filter") or "").strip().lower()
    keyword_filter = (sub.get("keyword_filter") or "").strip().lower()
    location_filter = (sub.get("location_filter") or "").strip().lower()
    term_filter = (sub.get("term_filter") or "").strip().lower()

    # If all filters are empty, matches everything
    if not company_filter and not keyword_filter and not location_filter and not term_filter:
        return True

    # Check company filter
    if company_filter:
        posting_company = (posting.get("company") or "").lower()
        if company_filter not in posting_company:
            return False

    # Check keyword filter in title
    if keyword_filter:
        posting_title = (posting.get("title") or "").lower()
        if keyword_filter not in posting_title:
            return False

    # Check location filter
    if location_filter:
        posting_loc = (posting.get("location") or "").lower()
        if location_filter not in posting_loc:
            return False

    # Check term / season filter (e.g. 'Summer 2027', 'Fall 2026')
    if term_filter:
        posting_terms = (posting.get("terms") or "").lower()
        posting_title = (posting.get("title") or "").lower()
        if term_filter not in posting_terms and term_filter not in posting_title:
            return False

    return True


def get_sent_posting_ids(conn: psycopg.Connection, user_id: int, posting_ids: list[int]) -> set[int]:
    """Return set of posting IDs already notified to this user."""
    if not posting_ids:
        return set()

    query = """
        SELECT posting_id FROM notifications_sent 
        WHERE user_id = %s AND posting_id = ANY(%s);
    """
    with conn.cursor() as cur:
        cur.execute(query, (user_id, posting_ids))
        rows = cur.fetchall()
        return {r["posting_id"] for r in rows}


def match_postings_for_users(
    conn: psycopg.Connection,
    new_postings: list[dict[str, Any]],
    mode: str = "instant",
) -> dict[int, list[dict[str, Any]]]:
    """
    Match newly ingested postings to users.
    Returns: {telegram_chat_id: [list of matched posting dicts]}
    """
    if not new_postings:
        return {}

    users = get_active_subscribers_with_subscriptions(conn, mode=mode)
    if not users:
        return {}

    posting_ids = [p["id"] for p in new_postings if "id" in p]
    user_matches: dict[int, list[dict[str, Any]]] = {}

    for user in users:
        user_id = user["user_id"]
        chat_id = user["telegram_chat_id"]
        subscriptions = user["subscriptions"]

        if not subscriptions:
            # User has no active subscriptions
            continue

        already_sent = get_sent_posting_ids(conn, user_id, posting_ids)
        matched_for_this_user: list[dict[str, Any]] = []

        for p in new_postings:
            p_id = p["id"]
            if p_id in already_sent:
                continue

            # Check against each subscription filter
            for sub in subscriptions:
                if matches_subscription(p, sub):
                    matched_for_this_user.append(p)
                    break  # Avoid duplicating the same posting if multiple filters match

        if matched_for_this_user:
            user_matches[chat_id] = matched_for_this_user

    return user_matches
