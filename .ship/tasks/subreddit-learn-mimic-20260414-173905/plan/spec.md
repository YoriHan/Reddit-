# Spec: Subreddit Style Learning + Mimic Post Generation (merged)

HEAD SHA: (no git)
Date: 2026-04-14
Diff applied: D1 concede, D2 concede, D3 proven-host-correct, D4 concede, D5 patched

---

## Problem Statement

Users want to:
1. Study a subreddit deeply (10 pages, ~250 posts) to understand its writing style, tone, culture, and norms
2. Generate a post that authentically fits that subreddit's style while naturally featuring their product

Currently the tool can fetch up to 100 posts in a single call but has no style analysis, no style caching, and no "mimic" writing mode.

---

## Architecture Overview

```
reddit-toolkit style learn --subreddit python
   ↓
style_learner.fetch_subreddit_corpus()  [NEW file]
   ↓ paginated: top-all + hot, ~250 posts, deduped
analyze_subreddit_style()               [writer.py — NEW function]
   ↓ top 200 posts by score, 100-char body truncation
style_store.save()                      [NEW file]
   → ~/.reddit-toolkit/styles/python.json

reddit-toolkit style mimic --subreddit python --product my-app
   ↓
style_store.load("python")
profile_store.load("my-app")  OR  --describe "..."
   ↓
generate_mimic_post()                   [writer.py — NEW function]
   ↓
print title + body
```

---

## Investigation Findings

### RedditClient (reddit_client.py:14)
- `get(path, params)` — single GET, no pagination built-in
- Reddit JSON API: pass `after=<fullname>` in params, response `data.after` has next cursor or `null`
- Built-in `time.sleep(1)` per request (rate-limit safe)
- Max `limit=100` per Reddit API call

### Content (content.py:30-53)
- All 4 functions make a single API call — stateless, no cursor support
- `_extract_posts()` and `_normalise_post()` are directly reusable for pagination loop

### Writer (writer.py)
- `_make_client()` + `_call_claude(client, system, user)` with default `max_tokens=1024` (line 24)
- `generate_opportunity_draft()` overrides to `max_tokens=2048` (line 223) — mimic generation follows same pattern
- All existing writer functions accept `profile: dict` for product context

### Profile Store (profile_store.py)
- Files at `~/.reddit-toolkit/profiles/<id>.json`
- Schema: `description`, `problem_solved`, `target_audience`, `key_features`, `tone`, `keywords` (lines 51-67)
- `slugify()` utility already exists (line 24) — reuse for style cache keys
- `_data_dir()` base dir pattern (line 13) — style store follows same pattern

### Scanner state pattern (scanner.py:20-23)
- `~/.reddit-toolkit/state/` — same base dir, created on demand
- Style cache follows: `~/.reddit-toolkit/styles/`

### Existing inline description pattern (cli_product.py:19)
- `elif args.description: raw_text = args.description` shows inline text is an established pattern
- Justifies supporting `--describe "..."` alongside `--product <id>`

---

## New Files

### `reddit_toolkit/style_learner.py`

Owns the pagination loop and corpus assembly. Distinct from `content.py` (which is stateless single-call).

```python
from .reddit_client import RedditClient
from .content import _extract_posts  # reuse normalisation

def fetch_subreddit_corpus(subreddit: str, pages: int = 10, per_page: int = 25, client=None) -> list:
    """Fetch posts from a subreddit across multiple pages. Returns list of normalised post dicts."""
    c = client or RedditClient()
    all_posts = []
    seen_permalinks = set()

    # Phase 1: top-all (most culturally representative)
    after = None
    for page_num in range(1, pages + 1):
        print(f"  Fetching page {page_num}/{pages}...", flush=True)
        params = {"limit": per_page, "t": "all"}
        if after:
            params["after"] = after
        response = c.get(f"/r/{subreddit}/top.json", params)
        batch = _extract_posts(response)
        if not batch:
            break
        for post in batch:
            if post["permalink"] not in seen_permalinks:
                seen_permalinks.add(post["permalink"])
                all_posts.append(post)
        after = response.get("data", {}).get("after")
        if not after:
            break

    # Phase 2: hot posts for recency signal
    response = c.get(f"/r/{subreddit}/hot.json", {"limit": 25})
    for post in _extract_posts(response):
        if post["permalink"] not in seen_permalinks:
            seen_permalinks.add(post["permalink"])
            all_posts.append(post)

    return all_posts
```

### `reddit_toolkit/style_store.py`

Mirrors `profile_store.py` structure exactly.

```python
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .profile_store import slugify  # reuse

class StyleNotFoundError(Exception):
    pass

def _data_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    return Path(base).expanduser()

def styles_dir() -> Path:
    d = _data_dir() / "styles"
    d.mkdir(parents=True, exist_ok=True)
    return d

def save(subreddit: str, data: dict) -> None:
    data["subreddit"] = subreddit.lower()
    data["learned_at"] = datetime.now(timezone.utc).isoformat()
    path = styles_dir() / f"{slugify(subreddit)}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load(subreddit: str) -> dict:
    path = styles_dir() / f"{slugify(subreddit)}.json"
    if not path.exists():
        raise StyleNotFoundError(
            f"No style profile for r/{subreddit}. "
            f"Run: reddit-toolkit style learn --subreddit {subreddit}"
        )
    with open(path) as f:
        return json.load(f)

def is_stale(data: dict, max_age_days: int = 7) -> bool:
    learned_at = data.get("learned_at")
    if not learned_at:
        return True
    dt = datetime.fromisoformat(learned_at)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)

def list_styles() -> list:
    return [json.loads(p.read_text()) for p in sorted(styles_dir().glob("*.json"))]
```

### `reddit_toolkit/cli_style.py`

Mirrors `cli_scan.py` structure.

```python
import sys
from .profile_store import load as load_profile, ProfileNotFoundError
from .style_store import load as load_style, list_styles, StyleNotFoundError, is_stale
from .style_learner import fetch_subreddit_corpus
from .writer import analyze_subreddit_style, generate_mimic_post, WriterConfigError
from .display import print_text
import contextlib, requests
from .reddit_client import RedditAPIError

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

def cmd_style_learn(args):
    with _reddit_errors():
        # Check staleness
        try:
            existing = load_style(args.subreddit)
            if not args.force and not is_stale(existing):
                age_days = ... # compute from learned_at
                print(f"Style profile for r/{args.subreddit} is fresh (learned {age_days} days ago). "
                      f"Use --force to re-learn.")
                return
        except StyleNotFoundError:
            pass

        print(f"Fetching r/{args.subreddit} corpus ({args.pages} pages)...")
        posts = fetch_subreddit_corpus(args.subreddit, pages=args.pages)
        print(f"  Fetched {len(posts)} posts total.")

        print("Analyzing writing style with AI...")
        try:
            style_data = analyze_subreddit_style(args.subreddit, posts)
        except WriterConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        from . import style_store
        style_store.save(args.subreddit, {"posts_analyzed": len(posts), "pages_fetched": args.pages, "style": style_data})

        print(f"\nStyle profile saved for r/{args.subreddit}.")
        print(f"  Tone: {style_data.get('tone', 'N/A')}")
        print(f"  Self-promo tolerance: {style_data.get('self_promotion_tolerance', 'N/A')}")
        print(f"  Title patterns: {len(style_data.get('common_title_patterns', []))} identified")

def cmd_style_mimic(args):
    # Load style profile
    try:
        cached = load_style(args.subreddit)
    except StyleNotFoundError as e:
        if not args.no_cache:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        # Inline learn with 5 pages
        print(f"No cache found. Fetching r/{args.subreddit} (5 pages)...")
        with _reddit_errors():
            posts = fetch_subreddit_corpus(args.subreddit, pages=5)
        try:
            style_data = analyze_subreddit_style(args.subreddit, posts)
        except WriterConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        from . import style_store
        style_store.save(args.subreddit, {"posts_analyzed": len(posts), "pages_fetched": 5, "style": style_data})
        cached = load_style(args.subreddit)

    # Load product info
    if args.product:
        try:
            profile = load_profile(args.product)
        except ProfileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        profile = {"name": "Product", "description": args.describe,
                   "problem_solved": "", "target_audience": [], "key_features": [], "tone": "casual", "keywords": []}

    # Generate
    try:
        result = generate_mimic_post(args.subreddit, cached["style"], profile, topic=args.topic or "")
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print_text(f"Mimic Post for r/{args.subreddit}", f"TITLE: {result['title']}\n\n{result['body']}")
    if args.verbose and result.get("why_it_fits"):
        print(f"\n[Why it fits: {result['why_it_fits']}]")

def cmd_style_list(args):
    styles = list_styles()
    if not styles:
        print("No style profiles cached yet.")
        return
    for s in styles:
        from .style_store import is_stale
        stale_marker = " [STALE]" if is_stale(s) else ""
        print(f"  r/{s['subreddit']} — {s.get('posts_analyzed', '?')} posts — learned {s.get('learned_at', '')[:10]}{stale_marker}")

def cmd_style_show(args):
    import json
    try:
        data = load_style(args.subreddit)
    except StyleNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, indent=2))
```

---

## Modified Files

### `reddit_toolkit/writer.py` — add two functions

**`analyze_subreddit_style(subreddit: str, posts: list) -> dict`**
- Sort posts by score descending, take top 200
- Truncate each body to 100 chars
- Call Claude with `max_tokens=2048`
- Return structured dict (tone, common_title_patterns, body_style, vocabulary_signals, community_norms, self_promotion_tolerance, successful_post_traits, raw_title_samples)

```python
def analyze_subreddit_style(subreddit: str, posts: list) -> dict:
    client = _make_client()
    top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:200]

    post_lines = []
    for p in top_posts:
        body_preview = (p.get("selftext") or "")[:100].replace("\n", " ")
        post_lines.append(f"TITLE: {p['title']} | SCORE: {p['score']} | BODY: {body_preview}")
    corpus_text = "\n".join(post_lines)

    system = (
        "You are a cultural analyst specializing in online communities. "
        "Analyze this Reddit post corpus and extract the community's writing style, "
        "tone, format conventions, and cultural norms. "
        "Return a JSON object only — no other text. "
        'Schema: {"tone": str, "formality": "low|medium|high", '
        '"common_title_patterns": [str], "body_style": str, '
        '"humor_level": str, "self_promotion_tolerance": str, '
        '"taboo_topics": [str], "vocabulary_signals": [str], '
        '"community_values": [str], "successful_post_traits": str, '
        '"raw_title_samples": [str]}'
    )
    user = (
        f"Subreddit: r/{subreddit}\n"
        f"Corpus ({len(top_posts)} posts, sorted by score):\n\n{corpus_text}"
    )
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return {"tone": raw[:200], "common_title_patterns": [], "body_style": "",
                "vocabulary_signals": [], "community_norms": "", "self_promotion_tolerance": "unknown",
                "raw_title_samples": [p["title"] for p in top_posts[:20]]}
```

**`generate_mimic_post(subreddit: str, style: dict, profile: dict, topic: str = "") -> dict`**
- Returns `{"title": str, "body": str, "why_it_fits": str}`
- `max_tokens=2048`

```python
def generate_mimic_post(subreddit: str, style: dict, profile: dict, topic: str = "") -> dict:
    client = _make_client()
    title_samples = "\n".join(f"- {t}" for t in style.get("raw_title_samples", [])[:10])
    system = (
        f"You are a native r/{subreddit} contributor. Write a Reddit post that fits this community "
        "perfectly — not an ad, but a genuine contribution that naturally mentions a product. "
        f"\n\nCommunity style guide:"
        f"\n- Tone: {style.get('tone', 'casual')}"
        f"\n- Formality: {style.get('formality', 'low')}"
        f"\n- Self-promotion tolerance: {style.get('self_promotion_tolerance', 'low')}"
        f"\n- Successful post traits: {style.get('successful_post_traits', '')}"
        f"\n- Common title patterns: {', '.join(style.get('common_title_patterns', []))}"
        f"\n- Community values: {', '.join(style.get('community_values', []))}"
        f"\n- Vocabulary to use: {', '.join(style.get('vocabulary_signals', []))}"
        f"\n- Topics to avoid: {', '.join(style.get('taboo_topics', []))}"
        f"\n\nExample high-performing titles:\n{title_samples}"
        f"\n\nProduct to mention naturally:"
        f"\nName: {profile.get('name', '')}"
        f"\nDescription: {profile.get('description', '')}"
        f"\nProblem solved: {profile.get('problem_solved', '')}"
        f"\nTarget audience: {', '.join(profile.get('target_audience', []))}"
        "\n\nRules: (1) community value first, product second "
        "(2) product mention feels incidental (3) match vocabulary exactly "
        "(4) respect self-promotion tolerance "
        '\nReturn JSON only: {"title": str, "body": str, "why_it_fits": str}'
    )
    post_type = topic if topic else "general contribution"
    user = f"Write a {post_type} post for r/{subreddit} that feels completely native."
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text
    try:
        result = _json.loads(raw)
        return {
            "title": result.get("title", ""),
            "body": result.get("body", ""),
            "why_it_fits": result.get("why_it_fits", ""),
        }
    except _json.JSONDecodeError:
        return {"title": "", "body": raw[:2000], "why_it_fits": ""}
```

### `reddit_toolkit/cli.py` — add `style` subparser

Add after the `notion` block (line ~287):

```python
from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show

style_parser = subparsers.add_parser("style", help="Learn subreddit style and generate mimic posts")
style_sub = style_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

# style learn
sl_p = style_sub.add_parser("learn", help="Learn writing style of a subreddit")
sl_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
sl_p.add_argument("--pages", "-p", type=int, default=10, help="Pages to fetch (default: 10)")
sl_p.add_argument("--force", action="store_true", help="Re-learn even if cache is fresh")
sl_p.set_defaults(func=cmd_style_learn)

# style mimic
sm_p = style_sub.add_parser("mimic", help="Generate a post mimicking the subreddit style")
sm_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
product_group = sm_p.add_mutually_exclusive_group(required=True)
product_group.add_argument("--product", help="Product profile ID")
product_group.add_argument("--describe", metavar="DESCRIPTION", help="Inline product description")
sm_p.add_argument("--topic", "-t", default="", help="Post angle hint (e.g. 'launch announcement')")
sm_p.add_argument("--verbose", "-v", action="store_true", help="Show why_it_fits analysis")
sm_p.add_argument("--no-cache", dest="no_cache", action="store_true",
                   help="Re-learn style before generating (5 pages)")
sm_p.set_defaults(func=cmd_style_mimic)

# style list
slist_p = style_sub.add_parser("list", help="List cached style profiles")
slist_p.set_defaults(func=cmd_style_list)

# style show
sshow_p = style_sub.add_parser("show", help="Show cached style profile")
sshow_p.add_argument("--subreddit", "-s", required=True)
sshow_p.set_defaults(func=cmd_style_show)
```

---

## CLI Interface (final)

```bash
# Learn
reddit-toolkit style learn --subreddit python
reddit-toolkit style learn --subreddit python --pages 20 --force

# Generate mimic post
reddit-toolkit style mimic --subreddit python --product my-app
reddit-toolkit style mimic --subreddit python --describe "A CLI tool for Python devs that..."
reddit-toolkit style mimic --subreddit python --product my-app --topic "asking for feedback"
reddit-toolkit style mimic --subreddit python --product my-app --no-cache --verbose

# Browse cached profiles
reddit-toolkit style list
reddit-toolkit style show --subreddit python
```

---

## Storage Schema

**`~/.reddit-toolkit/styles/<subreddit>.json`**

```json
{
  "subreddit": "python",
  "learned_at": "2026-04-14T10:00:00+00:00",
  "posts_analyzed": 247,
  "pages_fetched": 10,
  "style": {
    "tone": "informative-casual",
    "formality": "low",
    "common_title_patterns": ["I built X", "How do you..."],
    "body_style": "short intro + code block, rarely >300 words",
    "humor_level": "dry, moderate",
    "self_promotion_tolerance": "high if showing real work",
    "taboo_topics": ["politics", "off-topic memes"],
    "vocabulary_signals": ["pythonic", "PEP", "async", "type hints"],
    "community_values": ["learning", "open source", "sharing"],
    "successful_post_traits": "concrete demos, links to code, genuine questions",
    "raw_title_samples": ["..."]
  }
}
```

---

## Product Info (final recommendation)

**Two paths, one required:**

1. `--product <id>` → `profile_store.load(id)` — uses full profile (richest context)
2. `--describe "..."` → inline `{"name": "Product", "description": args.describe, ...}` — zero setup

**Rationale:** User's original question was "how should product info work" — supporting both paths gives the right answer: power users with profiles get the full richness; newcomers get instant access without a setup step. Evidence: `cli_product.py:19` shows inline description is already a first-class input pattern in this codebase.

---

## Edge Cases

| Case | Handling |
|------|----------|
| Subreddit not found / private | `RedditAPIError` → `_reddit_errors()` → stderr + exit(1) |
| Style cache missing on `mimic` without `--no-cache` | `StyleNotFoundError` → stderr + helpful message |
| Cache exists but stale | Print warning + exit (use `--force` to re-learn) |
| All posts are link-only (no selftext) | Analysis uses titles only — still valid |
| `data.after` null before reaching page count | Stop gracefully, proceed with what was fetched |
| `ANTHROPIC_API_KEY` missing | `WriterConfigError` → stderr + exit(1) |
| Subreddit name casing | `slugify()` lowercases storage key |
| `--product` and `--describe` both/neither | argparse `mutually_exclusive_group(required=True)` |

---

## Files Summary

| File | Action | Est. lines |
|------|--------|-----------|
| `style_store.py` | NEW | ~40 |
| `style_learner.py` | NEW | ~45 |
| `cli_style.py` | NEW | ~90 |
| `writer.py` | MODIFY — add `analyze_subreddit_style()`, `generate_mimic_post()` | +85 |
| `cli.py` | MODIFY — add `style` subparser block | +30 |

Total: ~290 lines across 5 files (3 new, 2 modified).

---

## Tests to Add

Following `tests/test_writer.py` mock pattern (`make_anthropic_mock` + `patch("reddit_toolkit.writer._make_client")`):

- `tests/test_style_store.py` — save/load/is_stale/list/StyleNotFoundError
- `tests/test_style_learner.py` — pagination loop, deduplication, hot phase, early stop on null after
- `tests/test_writer.py` — add `TestAnalyzeSubredditStyle`, `TestGenerateMimicPost`
