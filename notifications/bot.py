"""Interactive Telegram bot for managing job alert subscriptions and preferences."""

import os
from typing import Any
from dotenv import load_dotenv
from rich.console import Console
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from db.connection import get_db_connection

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
        f"📌 *Filter & Watch Commands:*\n"
        f"• `/watch term Summer 2027` — Alert for Summer 2027 cycle\n"
        f"• `/watch term Fall 2026` — Alert for Fall 2026 co-ops\n"
        f"• `/watch <company>` — Alert on company (e.g. `/watch Cloudflare`)\n"
        f"• `/watch keyword <term>` — Alert on keywords (e.g. `/watch keyword Data`)\n"
        f"• `/watch all` — Alert on every new posting\n\n"
        f"⚙️ *Settings & Management:*\n"
        f"• `/mode <instant|digest|pause>` — Set notification frequency\n"
        f"• `/list` — View your active filters\n"
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
        "🔍 *Term & Season Filters:*\n"
        "• `/watch term Summer 2027` — Track Summer 2027 internships\n"
        "• `/watch term Fall 2026` — Track Fall 2026 co-ops/internships\n"
        "• `/watch term Spring 2027` — Track Spring 2027 off-season\n\n"
        "🏢 *Company & Keyword Filters:*\n"
        "• `/watch Google` — Notifies when Google posts\n"
        "• `/watch keyword Software` — Notifies when title contains 'Software'\n"
        "• `/watch all` — Notifies on all incoming tech postings\n\n"
        "⚙️ *Notification Modes:*\n"
        "• `/mode instant` — Real-time pings when jobs are detected (default)\n"
        "• `/mode digest` — Aggregated daily evening summary\n"
        "• `/mode pause` — Temporarily mute all alerts\n\n"
        "📋 *Management:*\n"
        "• `/list` — Show your active filters and ID numbers\n"
        "• `/unwatch 3` — Delete filter #3\n"
        "• `/unwatch Google` — Delete filters matching Google\n"
        "• `/unwatch all` — Clear all filters"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


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
        # Wildcard subscription
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


def start_bot() -> None:
    """Start the Telegram bot daemon in polling mode."""
    if not TELEGRAM_BOT_TOKEN:
        console.print("[bold red]Error: TELEGRAM_BOT_TOKEN is not set in .env.[/]")
        console.print("Please set your bot token from @BotFather in .env to run the bot listener.")
        return

    console.print("[bold green]Starting Telegram Bot Listener...[/]")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("watch", watch_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("unwatch", unwatch_command))
    app.add_handler(CommandHandler("mode", mode_command))

    console.print("[bold green]✓ Telegram Bot is running and listening for commands.[/]")
    app.run_polling()


if __name__ == "__main__":
    start_bot()
