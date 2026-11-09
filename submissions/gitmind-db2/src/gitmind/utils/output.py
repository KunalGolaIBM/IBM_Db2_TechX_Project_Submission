"""
GitMind — Rich Output Formatting

Helpers for beautiful terminal output using Rich:
panels, tables, spinners, severity indicators, and markdown rendering.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.rule import Rule


console = Console()

#  PANELS & SECTIONS

def print_response(content: str, title: str = "GitMind"):
    """Print an agent response as a styled panel with markdown rendering."""
    md = Markdown(content)
    panel = Panel(
        md,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def print_section(title: str, content: str, style: str = "blue"):
    """Print a titled section."""
    console.print(Rule(title=title, style=style))
    console.print(content)
    console.print()


def print_error(message: str):
    """Print an error message."""
    console.print(f"[bold red]✗ Error:[/bold red] {message}")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


def print_success(message: str):
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[dim cyan]ℹ[/dim cyan] {message}")


#  SPINNERS & PROGRESS

@contextmanager
def spinner(message: str = "Thinking..."):
    """Context manager for a loading spinner."""
    with Live(
        Spinner("dots", text=Text(f" {message}", style="cyan")),
        console=console,
        transient=True,
    ):
        yield


#  TABLES

def print_commits_table(commits: list[dict], title: str = "Commits"):
    """Print commits in a formatted table."""
    table = Table(title=title, show_lines=False, border_style="dim")
    table.add_column("Hash", style="yellow", width=8)
    table.add_column("Date", style="dim", width=12)
    table.add_column("Author", style="green", width=20)
    table.add_column("Message", style="white")

    for commit in commits:
        table.add_row(
            commit.get("hash", "")[:8],
            str(commit.get("date", ""))[:10],
            commit.get("author", "")[:20],
            commit.get("message", "")[:60],
        )

    console.print(table)


def print_branches_table(branches: list[dict]):
    """Print branches in a formatted table."""
    table = Table(title="Branches", show_lines=False, border_style="dim")
    table.add_column("Branch", style="cyan")
    table.add_column("Current", style="green", width=8)
    table.add_column("Tracking", style="dim")
    table.add_column("Ahead/Behind", style="yellow", width=14)

    for branch in branches:
        current = "→" if branch.get("is_current") else ""
        tracking = branch.get("tracking", "—")
        ahead = branch.get("ahead", 0)
        behind = branch.get("behind", 0)
        ab = f"+{ahead}/-{behind}" if (ahead or behind) else "synced"

        table.add_row(branch["name"], current, tracking, ab)

    console.print(table)


#  CHAT MODE


def get_chat_input() -> Optional[str]:
    """Get user input in chat mode. Returns None on exit."""
    try:
        user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()
        if user_input.lower() in ("exit", "quit", "q", "bye"):
            return None
        return user_input
    except (KeyboardInterrupt, EOFError):
        return None


def print_chat_response(content: str):
    """Print agent response in chat mode."""
    console.print()
    md = Markdown(content)
    console.print(md)
    console.print()
