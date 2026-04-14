import argparse
import contextlib
import sys

import requests

from .content import get_hot_posts, get_top_posts, get_rising_posts, search_posts
from .subreddits import get_popular_subreddits, search_subreddits, get_subreddit_info, explore_by_topic
from .writer import generate_post_title, write_post_body, generate_comment, WriterConfigError
from .reddit_client import RedditAPIError
from .display import print_posts, print_subreddits, print_text


def _handle_error(msg: str, exit_code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


@contextlib.contextmanager
def _reddit_errors():
    """Catch Reddit API and network errors and exit with a user-facing message."""
    try:
        yield
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_hot(args):
    with _reddit_errors():
        posts = get_hot_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)


def cmd_content_top(args):
    with _reddit_errors():
        posts = get_top_posts(subreddit=args.subreddit, limit=args.limit, timeframe=args.time)
        print_posts(posts, verbose=args.verbose)


def cmd_content_rising(args):
    with _reddit_errors():
        posts = get_rising_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)


def cmd_content_search(args):
    with _reddit_errors():
        posts = search_posts(
            query=args.query,
            subreddit=args.subreddit,
            limit=args.limit,
            sort=args.sort,
        )
        print_posts(posts, verbose=args.verbose)


def cmd_subs_popular(args):
    with _reddit_errors():
        subs = get_popular_subreddits(limit=args.limit)
        print_subreddits(subs)


def cmd_subs_search(args):
    with _reddit_errors():
        subs = search_subreddits(query=args.query, limit=args.limit)
        print_subreddits(subs)


def cmd_subs_info(args):
    with _reddit_errors():
        sub = get_subreddit_info(args.subreddit)
        print(f"r/{sub['display_name']} — {sub['title']}")
        print(f"Subscribers: {sub['subscribers']:,}")
        print(f"URL: https://www.reddit.com{sub['url']}")
        if sub.get("description"):
            print(f"\nDescription:\n{sub['description']}")


def cmd_subs_explore(args):
    with _reddit_errors():
        subs = explore_by_topic(topic=args.topic, limit=args.limit)
        print_subreddits(subs)


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
            post_context=args.post_context or "",
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
    wc_p.add_argument("--post-context", default="", help="Additional context for the post (optional)")
    wc_p.add_argument("--tone", default="neutral",
                      choices=["neutral", "funny", "supportive", "critical"])
    wc_p.set_defaults(func=cmd_write_comment)

    # --- product ---
    from .cli_product import (
        cmd_product_create, cmd_product_list, cmd_product_show,
        cmd_product_add_subreddit, cmd_product_recommend_subreddits,
    )
    from .cli_scan import cmd_scan_run, cmd_scan_show, cmd_scan_setup_cron, cmd_scan_daemon
    from .cli_notion import cmd_notion_setup

    product_parser = subparsers.add_parser("product", help="Manage product profiles")
    product_sub = product_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    pc_p = product_sub.add_parser("create", help="Create a new product profile")
    pc_p.add_argument("--name", required=True, help="Product name")
    pc_p.add_argument("--description", default="", help="Product description")
    pc_p.add_argument("--from-file", default=None, metavar="FILE")
    pc_p.add_argument("--from-dir", default=None, metavar="DIR")
    pc_p.add_argument("--from-url", default=None, metavar="URL", help="Fetch product info from a URL")
    pc_p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    pc_p.set_defaults(func=cmd_product_create)

    pl_p = product_sub.add_parser("list", help="List all product profiles")
    pl_p.set_defaults(func=cmd_product_list)

    ps_p = product_sub.add_parser("show", help="Show a product profile")
    ps_p.add_argument("product_id")
    ps_p.set_defaults(func=cmd_product_show)

    pa_p = product_sub.add_parser("add-subreddit", help="Add a subreddit to a product")
    pa_p.add_argument("product_id")
    pa_p.add_argument("subreddit")
    pa_p.add_argument("--why", default="")
    pa_p.set_defaults(func=cmd_product_add_subreddit)

    pr_p = product_sub.add_parser("recommend-subreddits", help="AI-recommend subreddits")
    pr_p.add_argument("product_id")
    pr_p.add_argument("--limit", "-n", type=int, default=10)
    pr_p.set_defaults(func=cmd_product_recommend_subreddits)

    # --- scan ---
    scan_parser = subparsers.add_parser("scan", help="Scan Reddit for opportunities")
    scan_sub = scan_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    sr_p = scan_sub.add_parser("run", help="Run a scan for a product")
    sr_p.add_argument("--product", required=True)
    sr_p.add_argument("--threshold", type=int, default=None)
    sr_p.add_argument("--top", type=int, default=5)
    sr_p.add_argument("--dry-run", action="store_true")
    sr_p.add_argument("--notion", action="store_true", help="Push results to Notion after scan")
    sr_p.set_defaults(func=cmd_scan_run)

    ss_p = scan_sub.add_parser("show", help="Show recent scan results")
    ss_p.add_argument("--product", required=True)
    ss_p.add_argument("--last", type=int, default=20)
    ss_p.set_defaults(func=cmd_scan_show)

    sc_p = scan_sub.add_parser("setup-cron", help="Print a crontab line for scheduled scanning")
    sc_p.add_argument("--product", required=True)
    sc_p.add_argument("--hour", type=int, default=None, help="Run at this hour each day (0-23)")
    sc_p.add_argument("--minute", type=int, default=0)
    sc_p.add_argument("--every-hours", type=int, default=None, metavar="N", help="Run every N hours (e.g. 3)")
    sc_p.add_argument("--notion", action="store_true", help="Include --notion flag in cron command")
    sc_p.set_defaults(func=cmd_scan_setup_cron)

    # scan daemon
    sdaemon_p = scan_sub.add_parser("daemon", help="Run scan as an in-process daemon on a schedule")
    sdaemon_p.add_argument("--product", required=True, help="Product profile ID")
    sdaemon_p.add_argument("--interval", "-i", default="8h",
                            help="Scan interval (e.g. 8h, 30m, 1d). Default: 8h")
    sdaemon_p.set_defaults(func=cmd_scan_daemon)

    # --- notion ---
    notion_parser = subparsers.add_parser("notion", help="Manage Notion integration")
    notion_sub = notion_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    ns_p = notion_sub.add_parser("setup", help="Create or link a Notion database for a product")
    ns_p.add_argument("--product", required=True)
    ns_p.add_argument("--database-id", default=None, metavar="ID",
                      help="Link an existing Notion database instead of creating a new one")
    ns_p.set_defaults(func=cmd_notion_setup)

    # --- style ---
    from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show, cmd_style_match

    style_parser = subparsers.add_parser("style", help="Learn subreddit style and generate mimic posts")
    style_sub = style_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # style learn
    sl_p = style_sub.add_parser("learn", help="Learn the writing style of a subreddit")
    sl_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    sl_p.add_argument("--pages", "-p", type=int, default=10, help="Pages to fetch (default: 10)")
    sl_p.add_argument("--force", action="store_true", help="Re-learn even if cache is fresh")
    sl_p.set_defaults(func=cmd_style_learn)

    # style mimic
    sm_p = style_sub.add_parser("mimic", help="Generate a post mimicking the subreddit style")
    sm_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    product_group = sm_p.add_mutually_exclusive_group(required=True)
    product_group.add_argument("--product", help="Saved product profile ID")
    product_group.add_argument("--describe", metavar="DESCRIPTION",
                                help="Inline product description (no profile needed)")
    sm_p.add_argument("--topic", "-t", default="", help="Post angle hint (e.g. 'launch announcement')")
    sm_p.add_argument("--verbose", "-v", action="store_true",
                       help="Also print why_it_fits analysis")
    sm_p.add_argument("--no-cache", dest="no_cache", action="store_true",
                       help="Fetch fresh style data before generating (5 pages)")
    sm_p.add_argument("--notion", action="store_true", help="Push generated post to Notion")
    sm_p.set_defaults(func=cmd_style_mimic)

    # style list
    slist_p = style_sub.add_parser("list", help="List all cached style profiles")
    slist_p.set_defaults(func=cmd_style_list)

    # style show
    sshow_p = style_sub.add_parser("show", help="Show a cached style profile")
    sshow_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    sshow_p.set_defaults(func=cmd_style_show)

    # style match
    smatch_p = style_sub.add_parser("match", help="Find subreddits that fit your product and topic")
    product_group_m = smatch_p.add_mutually_exclusive_group(required=True)
    product_group_m.add_argument("--product", help="Saved product profile ID")
    product_group_m.add_argument("--describe", metavar="DESCRIPTION",
                                  help="Inline product description (no profile needed)")
    smatch_p.add_argument("--topic", "-t", default="", help="Post angle hint (e.g. 'launch announcement')")
    smatch_p.add_argument("--limit", "-n", type=int, default=5, help="Number of subreddits (default: 5)")
    smatch_p.set_defaults(func=cmd_style_match)

    # --- rules ---
    from .cli_rules import cmd_rules_learn, cmd_rules_show, cmd_rules_list

    rules_parser = subparsers.add_parser("rules", help="Manage subreddit rules and community norms")
    rules_sub = rules_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    rl_p = rules_sub.add_parser("learn", help="Fetch official rules and infer community norms")
    rl_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    rl_p.add_argument("--force", action="store_true", help="Re-learn even if cache is fresh")
    rl_p.set_defaults(func=cmd_rules_learn)

    rs_p = rules_sub.add_parser("show", help="Show cached rules for a subreddit")
    rs_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    rs_p.set_defaults(func=cmd_rules_show)

    rlist_p = rules_sub.add_parser("list", help="List all cached rule profiles")
    rlist_p.set_defaults(func=cmd_rules_list)

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
