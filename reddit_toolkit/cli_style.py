import contextlib
import json
import sys
from datetime import datetime, timezone

import requests

from .profile_store import load as load_profile, ProfileNotFoundError
from .reddit_client import RedditAPIError
from .style_store import load as load_style, list_styles, StyleNotFoundError, is_stale, save as save_style
from .style_learner import fetch_subreddit_corpus
from .writer import analyze_subreddit_style, generate_mimic_post, match_subreddits_for_topic, WriterConfigError
from .subreddits import get_subreddit_info
from .display import print_text
from .praw_client import make_praw_client_if_configured


@contextlib.contextmanager
def _reddit_errors():
    try:
        yield
    except RedditAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Error: Network error: could not connect to Reddit.", file=sys.stderr)
        sys.exit(1)


def _learn_subreddit(subreddit: str, pages: int) -> dict:
    """Shared helper: fetch corpus and analyze style. Returns full style cache dict."""
    with _reddit_errors():
        reddit_client = make_praw_client_if_configured()
        posts = fetch_subreddit_corpus(subreddit, pages=pages, client=reddit_client)
    print(f"  Fetched {len(posts)} posts total.")
    print("Analyzing writing style with AI...")
    style_data = analyze_subreddit_style(subreddit, posts)
    cache = {"posts_analyzed": len(posts), "pages_fetched": pages, "style": style_data}
    save_style(subreddit, cache)

    # Auto-learn rules using the already-fetched corpus
    try:
        from .rules_learner import learn_rules, RulesInferenceError
        from .rules_store import save as save_rules
        print("Analyzing community rules and norms...")
        rules_data = learn_rules(subreddit, posts=posts)
        save_rules(subreddit, rules_data)
        print(f"  Rules profile saved for r/{subreddit}.")
    except RulesInferenceError as e:
        print(f"  Warning: Rules inference failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  Warning: Could not learn rules: {e}", file=sys.stderr)

    return cache


def cmd_style_learn(args):
    # Check staleness
    try:
        existing = load_style(args.subreddit)
        if not args.force and not is_stale(existing):
            learned_at = existing.get("learned_at", "")
            try:
                dt = datetime.fromisoformat(learned_at)
                age_days = (datetime.now(timezone.utc) - dt).days
            except (ValueError, TypeError):
                age_days = "?"
            print(
                f"Style profile for r/{args.subreddit} is already fresh "
                f"(learned {age_days} day(s) ago). Use --force to re-learn."
            )
            return
    except StyleNotFoundError:
        pass

    print(f"Fetching r/{args.subreddit} corpus ({args.pages} pages)...")
    try:
        cache = _learn_subreddit(args.subreddit, args.pages)
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    style_data = cache["style"]
    print(f"\nStyle profile saved for r/{args.subreddit}.")
    print(f"  Tone: {style_data.get('tone', 'N/A')}")
    print(f"  Self-promo tolerance: {style_data.get('self_promotion_tolerance', 'N/A')}")
    patterns = style_data.get("common_title_patterns", [])
    print(f"  Title patterns: {len(patterns)} identified")
    vocab = style_data.get("vocabulary_signals", [])
    if vocab:
        print(f"  Vocabulary signals: {', '.join(vocab[:5])}")


def cmd_style_mimic(args):
    # Resolve style profile
    try:
        cached = load_style(args.subreddit)
    except StyleNotFoundError:
        if not args.no_cache:
            print(
                f"Error: No style profile for r/{args.subreddit}. "
                f"Run: reddit-toolkit style learn --subreddit {args.subreddit}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"No style cache found. Fetching r/{args.subreddit} (5 pages for speed)...")
        try:
            cached = _learn_subreddit(args.subreddit, pages=5)
        except WriterConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Load rules if cached (non-fatal if missing)
    rules_data = None
    try:
        from .rules_store import load as load_rules, RulesNotFoundError
        rules_data = load_rules(args.subreddit)
    except Exception:
        pass

    # Resolve product info
    if args.product:
        try:
            profile = load_profile(args.product)
        except ProfileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        profile = {
            "name": "Product",
            "description": args.describe,
            "problem_solved": "",
            "target_audience": [],
            "key_features": [],
            "tone": "casual",
            "keywords": [],
        }

    # Generate
    try:
        result = generate_mimic_post(
            args.subreddit,
            cached["style"],
            profile,
            topic=args.topic or "",
            rules=rules_data,
        )
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    content = f"TITLE: {result['title']}\n\n{result['body']}"
    print_text(f"Mimic Post for r/{args.subreddit}", content)
    if args.verbose and result.get("why_it_fits"):
        print(f"\n[Why it fits: {result['why_it_fits']}]")


def cmd_style_list(args):
    styles = list_styles()
    if not styles:
        print("No style profiles cached. Run: reddit-toolkit style learn --subreddit <name>")
        return
    for s in styles:
        stale_marker = " [STALE]" if is_stale(s) else ""
        learned = s.get("learned_at", "")[:10]
        posts = s.get("posts_analyzed", "?")
        print(f"  r/{s.get('subreddit', '?')} — {posts} posts — learned {learned}{stale_marker}")


def cmd_style_show(args):
    try:
        data = load_style(args.subreddit)
    except StyleNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, indent=2))


def cmd_style_match(args):
    # Resolve product info
    if args.product:
        try:
            profile = load_profile(args.product)
        except ProfileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        profile = {
            "name": "Product",
            "description": args.describe,
            "target_audience": [],
            "key_features": [],
        }

    topic_label = args.topic or "general post"
    print(f"Finding best subreddits for: {topic_label}...")
    try:
        candidates = match_subreddits_for_topic(profile, topic=args.topic or "", limit=args.limit)
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not candidates:
        print("No subreddits found. Try adjusting your topic or product description.", file=sys.stderr)
        sys.exit(1)

    # Enrich with real subscriber counts from Reddit API
    # Note: requests and RedditAPIError are already imported at module level
    # (cli_style.py:6 and cli_style.py:9) — no inline imports needed here
    enriched = []
    for c in candidates:
        try:
            info = get_subreddit_info(c["name"])
            c["subscribers"] = info["subscribers"]
        except (KeyError, RedditAPIError, requests.exceptions.ConnectionError):
            c["subscribers"] = None
        enriched.append(c)

    # Display results
    print(f"\nTop {len(enriched)} subreddits for \"{topic_label}\":\n")
    for i, s in enumerate(enriched, 1):
        subs = f"{s['subscribers']:,}" if s.get("subscribers") else "unknown"
        print(f"  {i}. r/{s['name']} — {subs} subscribers")
        print(f"     Why: {s['why']}")
        print(f"     Self-promo: {s.get('self_promo_tolerance', '?')}")
        print(f"     Angle: {s.get('post_angle', '')}")
        print()

    # Next-step hints for top result
    top = enriched[0]["name"]
    product_flag = f"--product {args.product}" if args.product else f'--describe "{args.describe}"'
    topic_flag = f' --topic "{args.topic}"' if args.topic else ""
    print("Next steps:")
    print(f"  reddit-toolkit style learn --subreddit {top}")
    print(f"  reddit-toolkit style mimic --subreddit {top} {product_flag}{topic_flag}")
