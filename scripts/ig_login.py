"""Interactive Instagram login helper to authenticate and export session cookies.

This script only needs to be run ONCE with your burner Instagram account.
It saves session cookies to `data/ig_session.json` so the automated poller
can query stories without sending login credentials or getting flagged.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from instagrapi import Client
from rich.console import Console
from rich.prompt import Prompt

console = Console()
load_dotenv()


def challenge_code_handler(username: str, choice: str) -> str:
    """Prompt user interactively for SMS or Email verification code if IG challenges."""
    console.print(f"[bold yellow]Instagram requested a verification code via {choice}![/]")
    return Prompt.ask("[bold cyan]Enter verification code received[/]").strip()


def login_and_save_session() -> None:
    session_path = Path(os.getenv("IG_SESSION_PATH", "data/ig_session.json"))
    session_path.parent.mkdir(parents=True, exist_ok=True)

    cl = Client()
    cl.challenge_code_handler = challenge_code_handler

    # 1. Test existing session if present
    if session_path.exists():
        console.print(f"[cyan]Found existing session file at [bold]{session_path}[/]. Testing validity...[/]")
        try:
            cl.load_settings(session_path)
            cl.get_timeline_feed()
            console.print("[bold green]✓ Session is valid and active! No new login needed.[/]")
            return
        except Exception as e:
            console.print(f"[yellow]Existing session expired or invalid ({e}). Logging in again...[/]")

    # 2. Collect credentials
    username = os.getenv("IG_USERNAME") or Prompt.ask("[bold cyan]Enter Burner Instagram Username[/]")
    password = os.getenv("IG_PASSWORD") or Prompt.ask("[bold cyan]Enter Burner Instagram Password[/]", password=True)

    if not username or not password:
        console.print("[bold red]Error: Username and password are required.[/]")
        return

    console.print(f"[cyan]Attempting login for user [bold]{username}[/]...[/]")

    # 3. Authenticate and handle 2FA/challenges
    try:
        # Prompt for 2FA code if 2-factor is enabled on the burner account
        two_factor_code = os.getenv("IG_2FA_CODE") or ""
        cl.login(username=username, password=password, verification_code=two_factor_code)
        
        # Save session settings
        cl.dump_settings(session_path)
        console.print(f"[bold green]✓ Login successful! Session saved to: [bold]{session_path}[/][/]")
        console.print("[green]The automated tracker will now use this session without needing your password.[/]")

    except Exception as exc:
        console.print(f"[bold red]Login failed:[/] {exc}")
        console.print("[dim]Tip: If Instagram shows a challenge or checkpoint, complete it on your phone or check email/SMS.[/]")


if __name__ == "__main__":
    login_and_save_session()
