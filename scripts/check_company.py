"""CLI helper to auto-detect a company's ATS provider and list active job postings."""

import sys
import httpx
from rich.console import Console
from rich.table import Table

console = Console()


def detect_ats(identifier: str) -> tuple[str | None, str, int]:
    """Auto-detect whether a company uses Greenhouse, Ashby, or Lever."""
    token = identifier.strip().lower()
    
    # Clean URLs if a user passes a full URL
    if "greenhouse.io/" in token:
        token = token.split("greenhouse.io/")[-1].split("/")[0]
        providers_to_test = ["greenhouse"]
    elif "ashbyhq.com/" in token:
        token = token.split("ashbyhq.com/")[-1].split("/")[0]
        providers_to_test = ["ashby"]
    elif "lever.co/" in token:
        token = token.split("lever.co/")[-1].split("/")[0]
        providers_to_test = ["lever"]
    else:
        providers_to_test = ["greenhouse", "ashby", "lever"]

    client = httpx.Client(timeout=8.0)

    for p in providers_to_test:
        if p == "greenhouse":
            try:
                r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
                if r.status_code == 200:
                    jobs = r.json().get("jobs", [])
                    return "greenhouse", token, len(jobs)
            except Exception:
                pass

        elif p == "ashby":
            try:
                r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
                if r.status_code == 200:
                    jobs = r.json().get("jobs", [])
                    return "ashby", token, len(jobs)
            except Exception:
                pass

        elif p == "lever":
            try:
                r = client.get(f"https://api.lever.co/v0/postings/{token}?mode=json")
                if r.status_code == 200 and isinstance(r.json(), list):
                    return "lever", token, len(r.json())
            except Exception:
                pass

    return None, token, 0


def main():
    if len(sys.argv) < 2:
        console.print("[yellow]Usage: uv run python scripts/check_company.py <company_name_or_url>[/]")
        console.print("[dim]Example: uv run python scripts/check_company.py linear[/]")
        return

    query = sys.argv[1]
    console.print(f"[bold cyan]Scanning ATS platforms for:[/] [bold]{query}[/]...")

    provider, token, count = detect_ats(query)

    if provider:
        console.print(f"[bold green]✓ Found active ATS board![/]")
        table = Table(title="Company ATS Metadata")
        table.add_column("Property", style="bold")
        table.add_column("Value", style="cyan")
        table.add_row("Detected ATS", provider.capitalize())
        table.add_row("Board Token", token)
        table.add_row("Active Roles", str(count))
        console.print(table)
        console.print(f"[dim]To track this company in Telegram, send:[/] [bold]/add_company {provider} {token}[/]")
    else:
        console.print(f"[bold red]✗ Could not find a public Greenhouse, Ashby, or Lever board for '{query}'.[/]")
        console.print("[dim]They might use a private portal (e.g. Workday, Oracle) or a custom subdomain.[/]")


if __name__ == "__main__":
    main()
