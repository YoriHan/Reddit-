from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def print_posts(posts, verbose=False, console=None):
    if console is None:
        console = Console()
    if not posts:
        console.print("[dim]No posts found.[/dim]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Title", max_width=60)
    if verbose:
        table.add_column("Score", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Date")
        table.add_column("URL")
    table.add_column("Subreddit")
    for i, post in enumerate(posts, 1):
        date_str = ""
        if verbose and post.get("created_utc"):
            date_str = datetime.utcfromtimestamp(post["created_utc"]).strftime("%Y-%m-%d")
        if verbose:
            table.add_row(
                str(i),
                post.get("title", ""),
                str(post.get("score", "")),
                str(post.get("num_comments", "")),
                date_str,
                post.get("url", ""),
                post.get("subreddit", ""),
            )
        else:
            table.add_row(str(i), post.get("title", ""), post.get("subreddit", ""))
    console.print(table)


def print_subreddits(subs, console=None):
    if console is None:
        console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Subreddit")
    table.add_column("Subscribers", justify="right")
    table.add_column("Description", max_width=50)
    for i, sub in enumerate(subs, 1):
        subs_str = f"{sub.get('subscribers', 0):,}" if sub.get("subscribers") else ""
        table.add_row(
            str(i),
            sub.get("display_name", ""),
            subs_str,
            sub.get("description", ""),
        )
    console.print(table)


def print_text(label, content, console=None):
    if console is None:
        console = Console()
    console.print(Panel(content, title=label))
