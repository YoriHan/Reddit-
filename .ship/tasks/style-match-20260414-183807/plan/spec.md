# Spec: `style match` — Topic-Aware Subreddit Matching

HEAD SHA: a48d201cab426c4be88381aacc5ca05ca4a84674

## Problem / Motivation

Current workflow gap: user has a product + topic they want to post about but must guess which subreddit to target. `product recommend-subreddits` (`writer.py:138`) does AI-only recommendation with no topic awareness, no subscriber counts, and no self-promo tolerance — not actionable for the mimic workflow.

New `style match` command fills step 0:
```
style match --product myapp --topic "launch announcement"
→ ranked list with subscriber counts + next-step commands to copy-paste
→ directly feeds into: style learn → style mimic
```

---

## Investigation Findings

### Analogous feature: `recommend_subreddits` (writer.py:138)
- `recommend_subreddits(profile: dict, limit: int = 10) -> list`
- Returns `[{"name": str, "why": str}]` — no topic, no subscriber counts
- Caller: `cli_product.py:85`

### `search_subreddits` (subreddits.py:31)
- Returns `[{display_name, title, subscribers, description, url}]`
- Keyword-based — misses semantically related subreddits

### `get_subreddit_info` (subreddits.py:36)
- Returns `_normalise_subreddit(data)` → `{display_name, title, subscribers, description, url}`
- Raises `KeyError` when response has no `data` key (subreddits.py:40)
- Used to enrich AI candidates with real subscriber counts

### `_normalise_subreddit` (subreddits.py:8)
- `subscribers` is in the normalized output
- Does NOT expose self-promo rules — Claude must estimate this

### `_call_claude` helper (writer.py:21)
- Signature: `_call_claude(client, system_prompt, user_prompt) -> str`
- Uses 1024 max_tokens (sufficient for a compact JSON array of 5 items)
- All existing writer functions use this helper; new function follows suit

### `_reddit_errors` context manager (cli_style.py:16)
- Already catches `RedditAPIError` and `requests.exceptions.ConnectionError`
- Same exceptions must be caught in enrichment loop (not the context manager — enrichment is per-item, not session-level)

### CLI wiring (cli.py:289-323)
- `style_sub` subparsers defined at line 293
- Import line at 290: `from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show`
- Adding `cmd_style_match` requires updating this import and adding subparser

### Test patterns (test_writer.py)
- `make_anthropic_mock(text_response)` helper at line 11 — reuse
- All writer functions imported at module level (lines 4-8)
- Pattern: `patch("reddit_toolkit.writer._make_client", return_value=mock_client)`

---

## Design Approach

**Hybrid: AI semantic candidates → Reddit API enriches with subscriber counts**

Why not pure AI: subscriber counts must be real.
Why not search-first: keyword search misses semantically related communities.

1. `match_subreddits_for_topic(profile, topic, limit)` in `writer.py` — Claude returns `[{name, why, self_promo_tolerance, post_angle}]`
2. `cmd_style_match` in `cli_style.py` — calls writer, then loops over results calling `get_subreddit_info(name)` to add real subscriber counts; skips any that fail
3. Display formatted results with copy-paste next-step commands

---

## Changes by File

### 1. `reddit_toolkit/writer.py` — ADD function

```python
def match_subreddits_for_topic(profile: dict, topic: str = "", limit: int = 5) -> list:
    """Recommend subreddits fit for a specific product + post topic.

    Returns list of {"name": str, "why": str, "self_promo_tolerance": str, "post_angle": str}
    """
    client = _make_client()
    system = (
        "You are a Reddit community expert. Given a product and a post topic/angle, "
        "recommend subreddits where this post would be genuinely welcomed. "
        "For each, estimate self-promotion tolerance (low/medium/high) based on community culture. "
        "Return a JSON array only — no other text. "
        f'Schema: [{{"name": "subreddit_name_without_r/", "why": "one sentence", '
        f'"self_promo_tolerance": "low|medium|high", "post_angle": "one sentence angle"}}]'
    )
    topic_line = f"\nPost topic/angle: {topic}" if topic else ""
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Target audience: {', '.join(profile.get('target_audience', []))}\n"
        f"Key features: {', '.join(profile.get('key_features', []))}"
        f"{topic_line}\n\n"
        f"Recommend {limit} subreddits."
    )
    raw = _call_claude(client, system, user)
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return []
```

### 2. `reddit_toolkit/cli_style.py` — ADD import + function

Add to top-level imports (after existing imports, line 13):
```python
from .subreddits import get_subreddit_info
from .writer import analyze_subreddit_style, generate_mimic_post, match_subreddits_for_topic, WriterConfigError
```

Note: `match_subreddits_for_topic` is added to the existing writer import line.

New function:
```python
def cmd_style_match(args):
    # Resolve product info (same pattern as cmd_style_mimic lines 97-112)
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
    import requests
    from .reddit_client import RedditAPIError
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
```

### 3. `reddit_toolkit/cli.py` — UPDATE import + ADD subparser

Line 290 — update import:
```python
from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show, cmd_style_match
```

After `sshow_p.set_defaults(func=cmd_style_show)` (line 323), add:
```python
# style match
smatch_p = style_sub.add_parser("match", help="Find subreddits that fit your product and topic")
product_group_m = smatch_p.add_mutually_exclusive_group(required=True)
product_group_m.add_argument("--product", help="Saved product profile ID")
product_group_m.add_argument("--describe", metavar="DESCRIPTION", help="Inline product description")
smatch_p.add_argument("--topic", "-t", default="", help="Post angle hint (e.g. 'launch announcement')")
smatch_p.add_argument("--limit", "-n", type=int, default=5, help="Number of subreddits (default: 5)")
smatch_p.set_defaults(func=cmd_style_match)
```

### 4. `tests/test_writer.py` — UPDATE import + ADD test class

Update top-level import (lines 4-8) to add `match_subreddits_for_topic`:
```python
from reddit_toolkit.writer import (
    generate_post_title, write_post_body, generate_comment, WriterConfigError,
    score_post_for_product, generate_opportunity_draft,
    extract_profile_from_text, recommend_subreddits,
    analyze_subreddit_style, generate_mimic_post,
    match_subreddits_for_topic,
)
```

New test class:
```python
class TestMatchSubredditsForTopic:
    def test_returns_list_with_expected_fields(self):
        mock_client = make_anthropic_mock(
            '[{"name": "python", "why": "Active dev community", '
            '"self_promo_tolerance": "medium", "post_angle": "Share as a tool"}]'
        )
        profile = {"name": "MyApp", "description": "...", "target_audience": [], "key_features": []}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = match_subreddits_for_topic(profile, topic="launch announcement")
        assert isinstance(result, list)
        assert result[0]["name"] == "python"
        assert "self_promo_tolerance" in result[0]
        assert "post_angle" in result[0]

    def test_topic_in_prompt(self):
        mock_client = make_anthropic_mock('[{"name": "p", "why": "r", "self_promo_tolerance": "low", "post_angle": "a"}]')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                match_subreddits_for_topic({}, topic="launch announcement", limit=3)
        messages = mock_client.messages.create.call_args.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "launch announcement" in prompt_text

    def test_no_topic_is_valid(self):
        mock_client = make_anthropic_mock('[{"name": "p", "why": "r", "self_promo_tolerance": "low", "post_angle": "a"}]')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = match_subreddits_for_topic({})
        assert isinstance(result, list)

    def test_parse_error_returns_empty_list(self):
        mock_client = make_anthropic_mock("not json")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = match_subreddits_for_topic({})
        assert result == []
```

---

## Acceptance Criteria

1. `reddit-toolkit style match --product <id> --topic "launch"` prints ranked subreddits with subscriber counts
2. `reddit-toolkit style match --describe "my tool" --topic "launch"` works without a saved profile
3. `--topic` is optional — omitting it produces a general post recommendation
4. Each result shows: rank, subreddit name, subscriber count (real from API), why, self-promo tolerance, post angle
5. If a suggested subreddit doesn't exist on Reddit, it's skipped gracefully (not crashed)
6. Output ends with copy-paste `style learn` + `style mimic` commands for top result
7. `--limit` controls result count (default 5)
8. Claude parse error → empty list → "No subreddits found" message + exit 1
9. `WriterConfigError` (no API key) → error message + exit 1

---

## Test Plan

- `TestMatchSubredditsForTopic` in `test_writer.py`: 4 tests
- `test_writer.py` top-level import updated with new function
- `cli_style.py` import updated to include `get_subreddit_info` + `match_subreddits_for_topic`

---

## Non-Goals

- No caching of match results
- No auto-launching `style learn` after match
- No modification to existing `product recommend-subreddits`
