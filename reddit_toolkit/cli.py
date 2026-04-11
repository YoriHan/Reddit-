import argparse
import sys

from .content import get_hot_posts, get_top_posts, get_rising_posts, search_posts
from .subreddits import get_popular_subreddits, search_subreddits, get_subreddit_info, explore_by_topic
from .writer import generate_post_title, write_post_body, generate_comment, WriterConfigError
from .reddit_client import RedditAPIError
from .display import print_posts, print_subreddits, print_text
import requests


def _handle_error(msg: str, exit_code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def cmd_content_hot(args):
    try:
        posts = get_hot_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_top(args):
    try:
        posts = get_top_posts(subreddit=args.subreddit, limit=args.limit, timeframe=args.time)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_rising(args):
    try:
        posts = get_rising_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_search(args):
    try:
        posts = search_posts(
            query=args.query,
            subreddit=args.subreddit,
            limit=args.limit,
            sort=args.sort,
        )
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_popular(args):
    try:
        subs = get_popular_subreddits(limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_search(args):
    try:
        subs = search_subreddits(query=args.query, limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_info(args):
    try:
        sub = get_subreddit_info(args.subreddit)
        print(f"r/{sub['display_name']} — {sub['title']}")
        print(f"Subscribers: {sub['subscribers']:,}")
        print(f"URL: https://www.reddit.com{sub['url']}")
        if sub.get("description"):
            print(f"\nDescription:\n{sub['description']}")
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_explore(args):
    try:
        subs = explore_by_topic(topic=args.topic, limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_write_title(args):
    try:
        titles = generate_post_title(
            subreddit=args.subreddit,
            topic=args.topic,
            context=args.context or "",
        )
        print_text("Post Title Suggestions", "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1)))
    except WriterConfigError as e:
        _handle_error(str(e))


def cmd_write_body(args):
    try:
        body = write_post_body(
            subreddit=args.subreddit,
            title=args.title,
            context=args.context or "",
        )
        print_text("Post Body", body)
    except WriterConfigError as e:
        _handle_error(str(e))


def cmd_write_comment(args):
    try:
        comment = generate_comment(
            post_title=args.post_title,
            post_body=args.post_body or "",
            tone=args.tone,
        )
        print_text("Comment", comment)
    except WriterConfigError as e:
        _handle_error(str(e))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reddit-toolkit",
        description="Discover Reddit content, explore subreddits, and write Reddit posts.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- content ---
    content_parser = subparsers.add_parser("content", help="Discover Reddit posts")
    content_sub = content_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # content hot
    hot_p = content_sub.add_parser("hot", help="Hot posts")
    hot_p.add_argument("--subreddit", "-s", default="all", help="Subreddit name (default: all)")
    hot_p.add_argument("--limit", "-n", type=int, default=10, help="Number of posts (default: 10)")
    hot_p.add_argument("--verbose", "-v", action="store_true", help="Show score, comments, date, URL")
    hot_p.set_defaults(func=cmd_content_hot)

    # content top
    top_p = content_sub.add_parser("top", help="Top posts")
    top_p.add_argument("--subreddit", "-s", default="all")
    top_p.add_argument("--limit", "-n", type=int, default=10)
    top_p.add_argument("--time", "-t", default="week",
                       choices=["hour", "day", "week", "month", "year", "all"],
                       help="Time filter (default: week)")
    top_p.add_argument("--verbose", "-v", action="store_true")
    top_p.set_defaults(func=cmd_content_top)

    # content rising
    rising_p = content_sub.add_parser("rising", help="Rising posts")
    rising_p.add_argument("--subreddit", "-s", default="all")
    rising_p.add_argument("--limit", "-n", type=int, default=10)
    rising_p.add_argument("--verbose", "-v", action="store_true")
    rising_p.set_defaults(func=cmd_content_rising)

    # content search
    search_p = content_sub.add_parser("search", help="Search posts")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--subreddit", "-s", default=None,
                          help="Restrict to subreddit (optional)")
    search_p.add_argument("--limit", "-n", type=int, default=10)
    search_p.add_argument("--sort", default="relevance",
                          choices=["relevance", "hot", "top", "new", "comments"])
    search_p.add_argument("--verbose", "-v", action="store_true")
    search_p.set_defaults(func=cmd_content_search)

    # --- subs ---
    subs_parser = subparsers.add_parser("subs", help="Discover subreddits")
    subs_sub = subs_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # subs popular
    pop_p = subs_sub.add_parser("popular", help="List popular subreddits")
    pop_p.add_argument("--limit", "-n", type=int, default=20)
    pop_p.set_defaults(func=cmd_subs_popular)

    # subs search
    ss_p = subs_sub.add_parser("search", help="Search subreddits")
    ss_p.add_argument("query", help="Search query")
    ss_p.add_argument("--limit", "-n", type=int, default=10)
    ss_p.set_defaults(func=cmd_subs_search)

    # subs info
    si_p = subs_sub.add_parser("info", help="Get subreddit info")
    si_p.add_argument("subreddit", help="Subreddit name")
    si_p.set_defaults(func=cmd_subs_info)

    # subs explore
    se_p = subs_sub.add_parser("explore", help="Explore subreddits by topic")
    se_p.add_argument("topic", help="Topic to explore")
    se_p.add_argument("--limit", "-n", type=int, default=10)
    se_p.set_defaults(func=cmd_subs_explore)

    # --- write ---
    write_parser = subparsers.add_parser("write", help="AI-powered writing assistance")
    write_sub = write_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # write title
    wt_p = write_sub.add_parser("title", help="Generate post title suggestions")
    wt_p.add_argument("--subreddit", "-s", required=True, help="Target subreddit")
    wt_p.add_argument("--topic", "-t", required=True, help="Post topic")
    wt_p.add_argument("--context", "-c", default="", help="Additional context")
    wt_p.set_defaults(func=cmd_write_title)

    # write body
    wb_p = write_sub.add_parser("body", help="Generate post body")
    wb_p.add_argument("--subreddit", "-s", required=True)
    wb_p.add_argument("--title", required=True, help="Post title")
    wb_p.add_argument("--context", "-c", default="")
    wb_p.set_defaults(func=cmd_write_body)

    # write comment
    wc_p = write_sub.add_parser("comment", help="Generate a comment")
    wc_p.add_argument("--post-title", required=True, help="Title of the post to comment on")
    wc_p.add_argument("--post-body", default="", help="Body of the post (optional)")
    wc_p.add_argument("--tone", default="neutral",
                      choices=["neutral", "funny", "supportive", "critical"])
    wc_p.set_defaults(func=cmd_write_comment)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
