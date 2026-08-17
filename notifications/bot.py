"""Interactive Telegram bot for managing job alert subscriptions, preferences, and instant job search."""

import os
from typing import Any
from dotenv import load_dotenv
from rich.console import Console
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from db.connection import get_db_connection
from notifications.dispatcher import format_batch_message

load_dotenv()
console = Console()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def ensure_user_registered(chat_id: int, username: str | None = None) -> dict[str, Any]:
    """Ensure user exists in the database and return user record."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (telegram_chat_id, username, notification_mode)
                VALUES (%s, %s, 'instant')
                ON CONFLICT (telegram_chat_id) 
                DO UPDATE SET username = COALESCE(EXCLUDED.username, users.username)
                RETURNING id, telegram_chat_id, username, notification_mode, digest_hour;
                """,
                (chat_id, username),
            )
            user = cur.fetchone()
        conn.commit()
        return user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    username = update.effective_user.username if update.effective_user else None
    user = ensure_user_registered(chat_id, username)

    welcome_text = (
        f"👋 *Welcome to Job & Internship Alert Tracker!*\n\n"
        f"You are registered (Chat ID: `{chat_id}`).\n"
        f"Current Mode: *{user['notification_mode']}*\n\n"
        f"🔍 *Instant Search & Links:*\n"
        f"• `/find Summer 2027` — Get latest Summer 2027 internship links\n"
        f"• `/find Stripe` — Get latest Stripe postings\n\n"
        f"🔔 *Watchlist & Auto-Alerts:*\n"
        f"• `/watch term Summer 2027` — Alert when new Summer 2027 jobs appear\n"
        f"• `/watch <company>` — Alert on specific company\n"
        f"• `/watch keyword <term>` — Alert on title keywords (e.g. `/watch keyword Intern`)\n"
        f"• `/watch all` — Alert on every new posting\n\n"
        f"⚙️ *Settings:*\n"
        f"• `/mode <instant|digest|pause>` — Set notification frequency\n"
        f"• `/list` — View active filters\n"
        f"• `/unwatch <id|name>` — Delete a filter\n"
        f"• `/help` — Full guide"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return

    help_text = (
        "📖 *Job Tracker Bot Commands:*\n\n"
        "🔎 *Instant Search & Browse Links:*\n"
        "• `/find Summer 2027` — Fetch active Summer 2027 openings with links\n"
        "• `/find Cloudflare` — Fetch latest Cloudflare jobs\n"
        "• `/find Data Engineer` — Search for specific roles\n\n"
        "🔔 *Continuous Auto-Alerts:*\n"
        "• `/watch term Summer 2027` — Real-time ping on new Summer 2027 jobs\n"
        "• `/watch term Fall 2026` — Real-time ping on Fall 2026 co-ops\n"
        "• `/watch Google` — Real-time ping when Google posts\n\n"
        "⚙️ *Notification Modes:*\n"
        "• `/mode instant` — Instant pings (default)\n"
        "• `/mode digest` — Aggregated daily evening summary\n"
        "• `/mode pause` — Temporarily mute all alerts\n\n"
        "📋 *Management:*\n"
        "• `/list` — Show your active filters\n"
        "• `/unwatch <id|name>` — Remove a filter\n"
        "• `/unwatch all` — Clear all filters"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search and return active job listings matching query immediately (supports optional count limit)."""
    if not update.effective_chat or not update.message:
        return

    args = context.args or []
    limit = 5

    # Check if the last argument is a numeric count (must be <= 50 and NOT a year like 2026/2027)
    if args and args[-1].isdigit():
        val = int(args[-1])
        if 1 <= val <= 50 and val not in range(2020, 2035):
            limit = min(val, 15)  # clamp to max 15
            query_str = " ".join(args[:-1]).strip()
        else:
            query_str = " ".join(args).strip()
    else:
        query_str = " ".join(args).strip()

    if not query_str:
        query_str = "Summer 2027"

    await update.message.reply_text(
        f"🔍 Searching database for *{query_str}* (showing top {limit})...",
        parse_mode=ParseMode.MARKDOWN,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, company, title, location, terms, is_remote, url, posted_at, first_seen_at
                FROM postings
                WHERE is_active = TRUE AND (
                    terms ILIKE %s OR 
                    company ILIKE %s OR 
                    title ILIKE %s OR 
                    search_vector @@ plainto_tsquery('english', %s)
                )
                ORDER BY posted_at DESC NULLS LAST, first_seen_at DESC
                LIMIT %s;
                """,
                (f"%{query_str}%", f"%{query_str}%", f"%{query_str}%", query_str, limit),
            )
            results = cur.fetchall()

    if not results:
        await update.message.reply_text(
            f"⚠️ No active postings found matching *{query_str}*.\nTry `/find Summer 2027` or `/find Replit`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chunks = format_batch_message(results, title=f"📋 *Active Postings Matching:* `{query_str}` ({len(results)} results)")
    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /watch command."""
    if not update.effective_chat or not update.message:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "⚠️ Please specify what to watch. Examples:\n"
            "• `/watch term Summer 2027`\n"
            "• `/watch term Fall 2026`\n"
            "• `/watch Stripe`\n"
            "• `/watch keyword Data`\n"
            "• `/watch all`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chat_id = update.effective_chat.id
    user = ensure_user_registered(chat_id, update.effective_user.username if update.effective_user else None)
    user_id = user["id"]

    first_arg = args[0].lower()
    company_filter = None
    keyword_filter = None
    term_filter = None

    if first_arg == "all":
        pass
    elif first_arg == "term" and len(args) > 1:
        term_filter = " ".join(args[1:])
    elif first_arg == "keyword" and len(args) > 1:
        keyword_filter = " ".join(args[1:])
    else:
        company_filter = " ".join(args)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions (user_id, company_filter, keyword_filter, term_filter)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (user_id, company_filter, keyword_filter, term_filter),
            )
            sub_id = cur.fetchone()["id"]
        conn.commit()

    if term_filter:
        msg = f"✓ Watching term / recruiting cycle: *{term_filter}* (ID: `{sub_id}`)"
    elif company_filter:
        msg = f"✓ Watching company: *{company_filter}* (ID: `{sub_id}`)"
    elif keyword_filter:
        msg = f"✓ Watching keyword: *{keyword_filter}* in title (ID: `{sub_id}`)"
    else:
        msg = f"✓ Watching *all new postings* (ID: `{sub_id}`)"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    user = ensure_user_registered(chat_id, update.effective_user.username if update.effective_user else None)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, company_filter, keyword_filter, location_filter, term_filter FROM subscriptions WHERE user_id = %s ORDER BY id ASC;",
                (user["id"],),
            )
            subs = cur.fetchall()

    if not subs:
        await update.message.reply_text(
            f"📋 You have no active subscriptions.\nCurrent Mode: *{user['notification_mode']}*\nUse `/watch term Summer 2027` or `/watch <company>` to add one!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = [f"📋 *Your Active Subscriptions* (Mode: *{user['notification_mode']}*):\n"]
    for s in subs:
        if s["term_filter"]:
            desc = f"Term / Cycle: *{s['term_filter']}*"
        elif s["company_filter"]:
            desc = f"Company: *{s['company_filter']}*"
        elif s["keyword_filter"]:
            desc = f"Keyword: *{s['keyword_filter']}*"
        else:
            desc = "*All Postings*"
        lines.append(f"• `[ID {s['id']}]` {desc}")

    lines.append("\n_Use `/unwatch <ID>` to remove a filter._")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def unwatch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unwatch command."""
    if not update.effective_chat or not update.message:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "⚠️ Please provide an ID or name to unwatch. Example: `/unwatch 3` or `/unwatch all`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chat_id = update.effective_chat.id
    user = ensure_user_registered(chat_id, update.effective_user.username if update.effective_user else None)
    target = " ".join(args).strip()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if target.lower() == "all":
                cur.execute("DELETE FROM subscriptions WHERE user_id = %s RETURNING id;", (user["id"],))
                deleted = cur.fetchall()
                msg = f"✓ Cleared all {len(deleted)} subscriptions."
            elif target.isdigit():
                cur.execute(
                    "DELETE FROM subscriptions WHERE user_id = %s AND id = %s RETURNING id;",
                    (user["id"], int(target)),
                )
                deleted = cur.fetchall()
                msg = f"✓ Removed subscription ID `{target}`." if deleted else f"⚠️ Subscription ID `{target}` not found."
            else:
                cur.execute(
                    """
                    DELETE FROM subscriptions 
                    WHERE user_id = %s AND (
                        LOWER(company_filter) = LOWER(%s) OR 
                        LOWER(term_filter) = LOWER(%s) OR
                        LOWER(keyword_filter) = LOWER(%s)
                    ) RETURNING id;
                    """,
                    (user["id"], target, target, target),
                )
                deleted = cur.fetchall()
                msg = (
                    f"✓ Removed {len(deleted)} subscription(s) matching *{target}*."
                    if deleted
                    else f"⚠️ No subscriptions found matching *{target}*."
                )
        conn.commit()

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mode command."""
    if not update.effective_chat or not update.message:
        return

    args = context.args or []
    valid_modes = {"instant", "digest", "daily_digest", "pause", "paused"}
    if not args or args[0].lower() not in valid_modes:
        await update.message.reply_text(
            "⚠️ Please specify a valid mode: `/mode instant`, `/mode digest`, or `/mode pause`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chosen = args[0].lower()
    db_mode = "instant"
    if chosen in ("digest", "daily_digest"):
        db_mode = "daily_digest"
    elif chosen in ("pause", "paused"):
        db_mode = "paused"

    chat_id = update.effective_chat.id
    user = ensure_user_registered(chat_id, update.effective_user.username if update.effective_user else None)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET notification_mode = %s WHERE id = %s;",
                (db_mode, user["id"]),
            )
        conn.commit()

    await update.message.reply_text(
        f"✓ Notification preference updated to: *{db_mode}*",
        parse_mode=ParseMode.MARKDOWN,
    )


async def add_company_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_company command to dynamically track new ATS boards."""
    if not update.effective_chat or not update.message:
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "🏢 *Add Custom Company ATS Board*\n\n"
            "*Usage:*\n"
            "`/add_company <greenhouse|lever|ashby> <board_token> [Company Name]`\n\n"
            "*Examples:*\n"
            "• `/add_company greenhouse anthropic Anthropic`\n"
            "• `/add_company ashby perplexity Perplexity`\n"
            "• `/add_company lever palantir Palantir`\n"
            "• `/add_company greenhouse figma Figma`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    provider = args[0].lower().strip()
    token = args[1].strip()
    display_name = " ".join(args[2:]).strip() if len(args) > 2 else token.capitalize()

    if provider not in ("greenhouse", "lever", "ashby"):
        await update.message.reply_text(
            "⚠️ Invalid provider. Supported ATS platforms: `greenhouse`, `lever`, `ashby`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update.message.reply_text(
        f"🔍 Verifying and polling *{display_name}* on `{provider}`...",
        parse_mode=ParseMode.MARKDOWN,
    )

    from ingestion.ats_watcher import MultiATSPoller
    from ingestion.runner import upsert_postings

    try:
        poller = MultiATSPoller(display_name, provider, token)
        postings = poller.poll()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO watched_companies (company_name, ats_provider, board_token, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (ats_provider, board_token) 
                    DO UPDATE SET company_name = EXCLUDED.company_name, is_active = TRUE;
                    """,
                    (display_name, provider, token),
                )
            conn.commit()

            inserted, updated, unmod = upsert_postings(conn, postings)

        await update.message.reply_text(
            f"✅ *Successfully added {display_name}!* 🎯\n\n"
            f"• *ATS Provider:* `{provider}`\n"
            f"• *Board Token:* `{token}`\n"
            f"• *Postings Ingested:* `{len(postings)}` active roles ({inserted} new)\n\n"
            f"Now monitoring `{display_name}` every 15 minutes! Use `/watch {display_name}` to get instant alerts.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to ingest from `{provider}:{token}`: {str(e)}",
            parse_mode=ParseMode.MARKDOWN,
        )


async def companies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /companies command to list all custom monitored ATS boards."""
    if not update.effective_chat or not update.message:
        return

    from ingestion.ats_watcher import load_all_watched_companies

    with get_db_connection() as conn:
        watched = load_all_watched_companies(conn)

    if not watched:
        await update.message.reply_text("No custom ATS company boards configured yet. Use `/add_company` to add one!")
        return

    lines = ["🏢 *Monitored Custom Company ATS Boards:*\n"]
    for w in sorted(watched, key=lambda x: x["company_name"]):
        lines.append(f"• *{w['company_name']}* (`{w['ats_provider']}:{w['board_token']}`)")

    lines.append("\n_Add more anytime with:_ `/add_company <greenhouse|lever|ashby> <token>`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


def start_bot() -> None:
    """Start the Telegram bot daemon in polling mode."""
    if not TELEGRAM_BOT_TOKEN:
        console.print("[bold red]Error: TELEGRAM_BOT_TOKEN is not set in .env.[/]")
        return

    console.print("[bold green]Starting Telegram Bot Listener...[/]")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("search", find_command))
    app.add_handler(CommandHandler("watch", watch_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("unwatch", unwatch_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("add_company", add_company_command))
    app.add_handler(CommandHandler("add_board", add_company_command))
    app.add_handler(CommandHandler("companies", companies_command))

    console.print("[bold green]✓ Telegram Bot is running and listening for commands.[/]")
    app.run_polling()


if __name__ == "__main__":
    start_bot()
