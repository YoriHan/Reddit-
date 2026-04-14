# Plan: Subreddit Style Learning + Mimic Post Generation

Task ID: subreddit-learn-mimic-20260414-173905
Spec: spec.md

---

## Stories

### Story 1: `style_store.py` — style cache persistence
**File:** `reddit_toolkit/style_store.py` (NEW)
**Dependencies:** none

- [ ] Create `reddit_toolkit/style_store.py` with the following complete content:

```python
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .profile_store import slugify


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

- [ ] Add tests in `tests/test_style_store.py`:

```python
import json
import pytest
from unittest.mock import patch
from pathlib import Path
import tempfile, os


@pytest.fixture
def tmp_data_dir(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        yield tmp_path


def test_save_and_load(tmp_data_dir):
    from reddit_toolkit.style_store import save, load
    data = {"style": {"tone": "casual"}}
    save("python", data)
    loaded = load("python")
    assert loaded["subreddit"] == "python"
    assert loaded["style"]["tone"] == "casual"
    assert "learned_at" in loaded


def test_load_not_found(tmp_data_dir):
    from reddit_toolkit.style_store import load, StyleNotFoundError
    with pytest.raises(StyleNotFoundError, match="reddit-toolkit style learn"):
        load("doesnotexist")


def test_slugify_normalization(tmp_data_dir):
    from reddit_toolkit.style_store import save, load
    save("Python", {"style": {}})
    loaded = load("python")  # lowercase lookup should work
    assert loaded["subreddit"] == "python"


def test_is_stale_old(tmp_data_dir):
    from reddit_toolkit.style_store import is_stale
    from datetime import datetime, timezone, timedelta
    old_dt = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    assert is_stale({"learned_at": old_dt}) is True


def test_is_stale_fresh(tmp_data_dir):
    from reddit_toolkit.style_store import is_stale
    from datetime import datetime, timezone
    fresh_dt = datetime.now(timezone.utc).isoformat()
    assert is_stale({"learned_at": fresh_dt}) is False


def test_list_styles(tmp_data_dir):
    from reddit_toolkit.style_store import save, list_styles
    save("python", {"style": {}})
    save("rust", {"style": {}})
    styles = list_styles()
    names = [s["subreddit"] for s in styles]
    assert "python" in names
    assert "rust" in names
```

---

### Story 2: `style_learner.py` — paginated corpus fetcher
**File:** `reddit_toolkit/style_learner.py` (NEW)
**Dependencies:** `content._extract_posts` (exists at content.py:22), `RedditClient` (reddit_client.py:10)

- [ ] Create `reddit_toolkit/style_learner.py` with the following complete content:

```python
from .reddit_client import RedditClient
from .content import _extract_posts


def fetch_subreddit_corpus(
    subreddit: str,
    pages: int = 10,
    per_page: int = 25,
    client=None,
) -> list:
    """Fetch posts from a subreddit across multiple pages.

    Fetches top-all posts (paginated) then hot posts for recency signal.
    Deduplicates by permalink. Respects RedditClient's built-in 1s rate limit.

    Returns:
        List of normalised post dicts (same schema as content._normalise_post)
    """
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

- [ ] Add tests in `tests/test_style_learner.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from reddit_toolkit.style_learner import fetch_subreddit_corpus

SAMPLE_POST = {
    "title": "Test post", "score": 100, "url": "https://x.com",
    "subreddit": "python", "author": "u1", "num_comments": 5,
    "permalink": "/r/python/comments/a/test/", "created_utc": 1700000000.0, "selftext": "",
}

def make_listing(posts, after=None):
    return {
        "data": {
            "after": after,
            "children": [{"kind": "t3", "data": p} for p in posts],
        }
    }


def make_client(responses):
    """responses: list of dicts returned in order."""
    client = MagicMock()
    client.get.side_effect = responses
    return client


def test_fetches_single_page_when_after_is_null():
    post = {**SAMPLE_POST}
    client = make_client([
        make_listing([post], after=None),  # top page 1
        make_listing([]),                  # hot
    ])
    result = fetch_subreddit_corpus("python", pages=10, per_page=25, client=client)
    assert len(result) == 1
    # Only called twice: 1 top page (after=None stops it) + 1 hot
    assert client.get.call_count == 2


def test_paginates_up_to_pages_limit():
    post1 = {**SAMPLE_POST, "permalink": "/a/"}
    post2 = {**SAMPLE_POST, "permalink": "/b/"}
    client = make_client([
        make_listing([post1], after="t3_abc"),  # top page 1
        make_listing([post2], after=None),       # top page 2 (after=None stops)
        make_listing([]),                         # hot
    ])
    result = fetch_subreddit_corpus("python", pages=5, per_page=25, client=client)
    assert len(result) == 2


def test_deduplicates_across_phases():
    post = {**SAMPLE_POST}
    client = make_client([
        make_listing([post], after=None),  # top
        make_listing([post]),              # hot — same permalink, should dedup
    ])
    result = fetch_subreddit_corpus("python", pages=1, client=client)
    assert len(result) == 1


def test_passes_after_cursor_to_second_page():
    post1 = {**SAMPLE_POST, "permalink": "/a/"}
    post2 = {**SAMPLE_POST, "permalink": "/b/"}
    client = make_client([
        make_listing([post1], after="t3_cursor123"),
        make_listing([post2], after=None),
        make_listing([]),
    ])
    fetch_subreddit_corpus("python", pages=5, per_page=10, client=client)
    second_call_params = client.get.call_args_list[1].args[1]
    assert second_call_params["after"] == "t3_cursor123"


def test_stops_early_if_empty_batch():
    client = make_client([
        make_listing([]),  # empty on first page → break immediately
        make_listing([]),  # hot
    ])
    result = fetch_subreddit_corpus("python", pages=10, client=client)
    assert result == []
```

---

### Story 3: `writer.py` — `analyze_subreddit_style` and `generate_mimic_post`
**File:** `reddit_toolkit/writer.py` (MODIFY — append two functions)
**Dependencies:** `_make_client()` (writer.py:11), `_call_claude()` (writer.py:21) are already defined

Note: `_call_claude` uses `max_tokens=1024`. The new functions need `max_tokens=2048`, so they call `client.messages.create` directly (same pattern as `generate_opportunity_draft` at writer.py:223).

- [ ] Append to `reddit_toolkit/writer.py`:

```python
def analyze_subreddit_style(subreddit: str, posts: list) -> dict:
    """Analyze a corpus of Reddit posts and extract the subreddit's writing style.

    Takes up to 200 top-scoring posts, truncates bodies to 100 chars each,
    and asks Claude to identify style patterns.

    Returns:
        dict with keys: tone, formality, common_title_patterns, body_style,
        humor_level, self_promotion_tolerance, taboo_topics, vocabulary_signals,
        community_values, successful_post_traits, raw_title_samples
    """
    client = _make_client()
    top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:200]

    post_lines = []
    for p in top_posts:
        body_preview = (p.get("selftext") or "")[:100].replace("\n", " ")
        post_lines.append(
            f"TITLE: {p['title']} | SCORE: {p['score']} | BODY: {body_preview}"
        )
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
        return {
            "tone": raw[:200],
            "formality": "low",
            "common_title_patterns": [],
            "body_style": "",
            "humor_level": "",
            "self_promotion_tolerance": "unknown",
            "taboo_topics": [],
            "vocabulary_signals": [],
            "community_values": [],
            "successful_post_traits": "",
            "raw_title_samples": [p["title"] for p in top_posts[:20]],
        }


def generate_mimic_post(
    subreddit: str, style: dict, profile: dict, topic: str = ""
) -> dict:
    """Generate a Reddit post that mimics a subreddit's style while featuring a product.

    Args:
        subreddit: Target subreddit name
        style: Style dict from analyze_subreddit_style
        profile: Product profile dict (from profile_store or inline)
        topic: Optional post angle hint (e.g. 'launch announcement')

    Returns:
        {"title": str, "body": str, "why_it_fits": str}
    """
    client = _make_client()
    title_samples = "\n".join(
        f"- {t}" for t in style.get("raw_title_samples", [])[:10]
    )
    system = (
        f"You are a native r/{subreddit} contributor. Write a Reddit post that fits "
        "this community perfectly — not an ad, but a genuine contribution that "
        "naturally mentions a product where relevant. "
        f"\n\nCommunity style guide:"
        f"\n- Tone: {style.get('tone', 'casual')}"
        f"\n- Formality: {style.get('formality', 'low')}"
        f"\n- Self-promotion tolerance: {style.get('self_promotion_tolerance', 'low')}"
        f"\n- Successful post traits: {style.get('successful_post_traits', '')}"
        f"\n- Common title patterns: {', '.join(style.get('common_title_patterns', []))}"
        f"\n- Community values: {', '.join(style.get('community_values', []))}"
        f"\n- Vocabulary to use naturally: {', '.join(style.get('vocabulary_signals', []))}"
        f"\n- Topics to avoid: {', '.join(style.get('taboo_topics', []))}"
        f"\n\nExample high-performing titles:\n{title_samples}"
        f"\n\nProduct to mention naturally:"
        f"\nName: {profile.get('name', '')}"
        f"\nDescription: {profile.get('description', '')}"
        f"\nProblem solved: {profile.get('problem_solved', '')}"
        f"\nTarget audience: {', '.join(profile.get('target_audience', []))}"
        "\n\nRules:"
        "\n1. Community value first — product mention is secondary"
        "\n2. Product mention must feel incidental, not the headline"
        "\n3. Match vocabulary and formatting exactly as seen in examples"
        "\n4. Respect the self-promotion tolerance level"
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

- [ ] Add to `tests/test_writer.py` (append two new test classes):

```python
class TestAnalyzeSubredditStyle:
    def test_returns_style_dict(self):
        mock_client = make_anthropic_mock(
            '{"tone": "casual", "formality": "low", "common_title_patterns": ["I built X"], '
            '"body_style": "short", "humor_level": "moderate", "self_promotion_tolerance": "high", '
            '"taboo_topics": [], "vocabulary_signals": ["pythonic"], "community_values": ["learning"], '
            '"successful_post_traits": "demos", "raw_title_samples": ["A title"]}'
        )
        posts = [{"title": "test", "score": 100, "selftext": "body text", "permalink": "/a/"}]
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import analyze_subreddit_style
                result = analyze_subreddit_style("python", posts)
        assert result["tone"] == "casual"
        assert isinstance(result["common_title_patterns"], list)

    def test_truncates_to_200_posts(self):
        mock_client = make_anthropic_mock('{"tone": "t", "formality": "low", "common_title_patterns": [], '
            '"body_style": "", "humor_level": "", "self_promotion_tolerance": "", '
            '"taboo_topics": [], "vocabulary_signals": [], "community_values": [], '
            '"successful_post_traits": "", "raw_title_samples": []}')
        posts = [{"title": f"post {i}", "score": i, "selftext": "", "permalink": f"/{i}/"} for i in range(300)]
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import analyze_subreddit_style
                analyze_subreddit_style("python", posts)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        # Corpus should contain at most 200 posts
        assert user_content.count("TITLE:") <= 200

    def test_parse_error_returns_fallback(self):
        mock_client = make_anthropic_mock("not json")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import analyze_subreddit_style
                result = analyze_subreddit_style("python", [])
        assert isinstance(result, dict)
        assert "tone" in result


class TestGenerateMimicPost:
    def test_returns_title_body_why(self):
        mock_client = make_anthropic_mock(
            '{"title": "I built a Reddit scanner", "body": "Long post body here...", '
            '"why_it_fits": "Matches I built X pattern"}'
        )
        style = {"tone": "casual", "formality": "low", "self_promotion_tolerance": "high",
                 "successful_post_traits": "demos", "common_title_patterns": ["I built X"],
                 "community_values": ["learning"], "vocabulary_signals": ["pythonic"],
                 "taboo_topics": [], "raw_title_samples": ["I built a tool"]}
        profile = {"name": "MyApp", "description": "Scans Reddit", "problem_solved": "saves time",
                   "target_audience": ["developers"], "tone": "casual"}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import generate_mimic_post
                result = generate_mimic_post("python", style, profile)
        assert result["title"] == "I built a Reddit scanner"
        assert result["body"] == "Long post body here..."
        assert "why_it_fits" in result

    def test_uses_2048_max_tokens(self):
        mock_client = make_anthropic_mock('{"title": "t", "body": "b", "why_it_fits": "w"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import generate_mimic_post
                generate_mimic_post("python", {}, {})
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 2048

    def test_topic_appears_in_prompt(self):
        mock_client = make_anthropic_mock('{"title": "t", "body": "b", "why_it_fits": "w"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import generate_mimic_post
                generate_mimic_post("python", {}, {}, topic="launch announcement")
        user_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "launch announcement" in user_content

    def test_parse_error_returns_fallback(self):
        mock_client = make_anthropic_mock("not json at all")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import generate_mimic_post
                result = generate_mimic_post("python", {}, {})
        assert result["title"] == ""
        assert len(result["body"]) > 0
```

---

### Story 4: `cli_style.py` — CLI commands
**File:** `reddit_toolkit/cli_style.py` (NEW)
**Dependencies:** Stories 1, 2, 3 must be complete first

- [ ] Create `reddit_toolkit/cli_style.py` with the following complete content:

```python
import contextlib
import json
import sys
from datetime import datetime, timezone

import requests

from .profile_store import load as load_profile, ProfileNotFoundError
from .reddit_client import RedditAPIError
from .style_store import load as load_style, list_styles, StyleNotFoundError, is_stale, save as save_style
from .style_learner import fetch_subreddit_corpus
from .writer import analyze_subreddit_style, generate_mimic_post, WriterConfigError
from .display import print_text


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
        posts = fetch_subreddit_corpus(subreddit, pages=pages)
    print(f"  Fetched {len(posts)} posts total.")
    print("Analyzing writing style with AI...")
    style_data = analyze_subreddit_style(subreddit, posts)
    cache = {"posts_analyzed": len(posts), "pages_fetched": pages, "style": style_data}
    save_style(subreddit, cache)
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
```

---

### Story 5: `cli.py` — wire `style` subparser
**File:** `reddit_toolkit/cli.py` (MODIFY)
**Dependencies:** Story 4 must be complete first

- [ ] In `reddit_toolkit/cli.py`, add the `style` subparser block after the notion block (after line 287, before the closing `return parser`):

```python
    # --- style ---
    from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show

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
    sm_p.set_defaults(func=cmd_style_mimic)

    # style list
    slist_p = style_sub.add_parser("list", help="List all cached style profiles")
    slist_p.set_defaults(func=cmd_style_list)

    # style show
    sshow_p = style_sub.add_parser("show", help="Show a cached style profile")
    sshow_p.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    sshow_p.set_defaults(func=cmd_style_show)
```

- [ ] Verify insertion point: `cli.py:287` ends with `ns_p.set_defaults(func=cmd_notion_setup)`. The style block goes on the next line, then the existing `return parser` (line 289) follows.

---

## Execution Order

Stories 1 and 2 are independent — implement in parallel.
Story 3 requires only existing `writer.py` functions — independent.
Story 4 requires Stories 1, 2, 3.
Story 5 requires Story 4.

**Wave 1 (parallel):** Stories 1, 2, 3
**Wave 2 (sequential):** Story 4 → Story 5

---

## Verification

After all stories:

```bash
cd /Users/yorihan/Reddit小工具
python -m pytest tests/ -v
reddit-toolkit style --help
reddit-toolkit style learn --help
reddit-toolkit style mimic --help
```

Expected: all existing tests pass, new tests pass, help output shows `style` command.
