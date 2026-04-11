from datetime import datetime, timezone


def _format_timestamp(utc_ts: float) -> str:
    """Convert Unix timestamp to human-readable UTC date string."""
    try:
        dt = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError, TypeError):
        return "unknown date"


def print_posts(posts: list, verbose: bool = False) -> None:
    """Print a numbered list of Reddit posts."""
    if not posts:
        print("No posts found.")
        return
    for i, post in enumerate(posts, 1):
        print(f"{i}. {post['title']}")
        if verbose:
            print(f"   Score: {post['score']}  |  Comments: {post['num_comments']}")
            print(f"   Posted: {_format_timestamp(post['created_utc'])}")
            print(f"   URL: {post.get('url', 'N/A')}")
            print(f"   Author: u/{post.get('author', 'unknown')}")
            print()


def print_subreddits(subreddits: list) -> None:
    """Print a numbered list of subreddits with metadata."""
    if not subreddits:
        print("No subreddits found.")
        return
    for i, sub in enumerate(subreddits, 1):
        subscribers = f"{sub['subscribers']:,}"
        print(f"{i}. r/{sub['display_name']} — {subscribers} subscribers")
        if sub.get("description"):
            desc = sub["description"]
            if len(desc) > 100:
                desc = desc[:97] + "..."
            print(f"   {desc}")


def print_text(label: str, content: str) -> None:
    """Print a labelled text block."""
    print(f"\n=== {label} ===")
    print(content)
    print("=" * (len(label) + 8))
