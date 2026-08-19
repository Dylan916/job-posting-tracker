"""Main pipeline runner: Orchestrates polling, change detection, and notification dispatch."""

import argparse
import os
import time
from rich.console import Console

from ingestion.runner import run_all_pollers
from notifications.dispatcher import dispatch_notifications

console = Console()


def run_pipeline_cycle(mode: str = "instant") -> None:
    """Execute a single end-to-end ingestion and notification cycle."""
    console.rule("[bold blue]Job Posting Tracker Pipeline Run[/]")
    
    # 1. Ingest from all sources and detect new postings
    new_postings, stats = run_all_pollers()

    # 2. Dispatch notifications to subscribed users
    if new_postings:
        console.print(f"[bold yellow]Dispatching notifications for {len(new_postings)} new posting(s)...[/]")
        sent_count = dispatch_notifications(new_postings, mode=mode)
        console.print(f"[bold green]✓ Dispatched {sent_count} notification alerts.[/]")
    else:
        console.print("[dim green]Pipeline cycle complete: No new postings to notify.[/]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-Time Internship/Job Posting Pipeline")
    parser.add_argument("--once", action="store_true", help="Run a single poll cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously on an interval")
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("POLL_INTERVAL_SECONDS", "900")),
        help="Poll interval in seconds (default: 900)",
    )
    parser.add_argument("--digest", action="store_true", help="Trigger daily digest dispatch")

    args = parser.parse_args()

    if args.digest:
        console.print("[bold cyan]Running Daily Digest Dispatch...[/]")
        run_pipeline_cycle(mode="daily_digest")
        return

    if args.loop:
        console.print(f"[bold green]Starting continuous polling loop every {args.interval}s (Ctrl+C to stop)...[/]")
        while True:
            try:
                run_pipeline_cycle(mode="instant")
                console.print(f"[dim]Sleeping for {args.interval} seconds...[/]")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping poller loop gracefully.[/]")
                break
    else:
        # Default is single run
        run_pipeline_cycle(mode="instant")


if __name__ == "__main__":
    main()
