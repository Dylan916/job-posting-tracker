"""Notification delivery dispatcher for Telegram with batching and deduplication."""

import asyncio
import os
from typing import Any
import psycopg
from rich.console import Console
from rich.panel import Panel
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from db.connection import get_db_connection
from notifications.matcher import match_postings_for_users

console = Console()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def format_posting_item(posting: dict[str, Any]) -> str:
    """Format a single posting for Telegram Markdown message."""
    company = posting.get("company", "Unknown")
    title = posting.get("title", "Untitled Role")
    location = posting.get("location") or "Not specified"
    terms = posting.get("terms")
    is_remote = posting.get("is_remote", False)
    url = posting.get("url") or "#"
    source = posting.get("source", "aggregator")

    remote_badge = " 🌐 *(Remote)*" if is_remote else ""
    term_line = f"📅 _{terms}_\n" if terms else ""

    return (
        f"🏢 *{company}*\n"
        f"💼 *{title}*{remote_badge}\n"
        f"{term_line}"
        f"📍 _{location}_\n"
        f"🔗 [Apply Here]({url}) | 🏷️ `{source}`\n"
    )


def format_batch_message(postings: list[dict[str, Any]], title: str = "🚨 *New Matching Job Openings*") -> list[str]:
    """Group postings into Telegram-compliant message chunks (max 4000 characters)."""
    chunks: list[str] = []
    current_chunk = f"{title}\n\n"

    for i, p in enumerate(postings, 1):
        item_text = f"*{i}.* " + format_posting_item(p) + "\n"
        if len(current_chunk) + len(item_text) > 3800:
            chunks.append(current_chunk)
            current_chunk = item_text
        else:
            current_chunk += item_text

    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks


def record_notifications_sent(conn: psycopg.Connection, user_chat_id: int, postings: list[dict[str, Any]]) -> None:
    """Record successfully dispatched notifications into notifications_sent."""
    with conn.cursor() as cur:
        # Lookup user_id from chat_id
        cur.execute("SELECT id FROM users WHERE telegram_chat_id = %s;", (user_chat_id,))
        user_row = cur.fetchone()
        if not user_row:
            return
        user_id = user_row["id"]

        query = """
            INSERT INTO notifications_sent (posting_id, user_id, sent_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (posting_id, user_id) DO NOTHING;
        """
        for p in postings:
            cur.execute(query, (p["id"], user_id))
    conn.commit()


async def send_telegram_messages(bot: Bot, chat_id: int, message_chunks: list[str]) -> bool:
    """Send batched messages to a Telegram chat with markdown fallback."""
    for chunk in message_chunks:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        except TelegramError as e:
            # Fallback to plain text if Markdown parsing failed
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk.replace("*", "").replace("_", "").replace("`", ""),
                    disable_web_page_preview=True,
                )
            except Exception as fallback_exc:
                console.print(f"[bold red]Failed to deliver to chat {chat_id}:[/] {fallback_exc}")
                return False
    return True


async def dispatch_notifications_async(
    new_postings: list[dict[str, Any]], mode: str = "instant"
) -> int:
    """Dispatch notifications to matched subscribers via Telegram."""
    if not new_postings:
        return 0

    with get_db_connection() as conn:
        user_matches = match_postings_for_users(conn, new_postings, mode=mode)
        if not user_matches:
            console.print("[dim]No user subscriptions matched the newly detected postings.[/]")
            return 0

        total_dispatched = 0

        if not TELEGRAM_BOT_TOKEN:
            console.print("[yellow]TELEGRAM_BOT_TOKEN not configured in .env. Running in Mock Dispatch Mode:[/]")
            for chat_id, matches in user_matches.items():
                chunks = format_batch_message(matches)
                console.print(Panel(
                    "\n".join(chunks),
                    title=f"[bold green]Mock Telegram Dispatch -> Chat ID {chat_id} ({len(matches)} jobs)[/]",
                    border_style="green",
                ))
                record_notifications_sent(conn, chat_id, matches)
                total_dispatched += len(matches)
            return total_dispatched

        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        for chat_id, matches in user_matches.items():
            chunks = format_batch_message(matches)
            success = await send_telegram_messages(bot, chat_id, chunks)
            if success:
                record_notifications_sent(conn, chat_id, matches)
                total_dispatched += len(matches)
                console.print(f"[green]✓ Delivered {len(matches)} job alerts to Telegram chat {chat_id}[/]")

        return total_dispatched


def dispatch_notifications(new_postings: list[dict[str, Any]], mode: str = "instant") -> int:
    """Synchronous entry point for notification dispatch."""
    return asyncio.run(dispatch_notifications_async(new_postings, mode=mode))
