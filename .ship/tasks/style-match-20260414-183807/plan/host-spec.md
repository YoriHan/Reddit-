# Host Spec: `style match` — Topic-Aware Subreddit Matching

## Problem / Motivation

Current workflow gap: user has a product + topic they want to post about, but has to guess which subreddit to target. `product recommend-subreddits` (writer.py:138) does AI-only recommendation with no topic awareness, no subscriber counts, and no self-promo tolerance — not actionable for the mimic workflow.

We need a `style match` command that:
1. Takes product info + topic angle
2. Returns a ranked list of subreddits fit for that specific post
3. Enriches each with real subscriber count from Reddit API
4. Outputs commands the user can immediately run

---

## Investigation Findings

### Existing `recommend_subreddits` (writer.py:138)
- Signature: `recommend_subreddits(profile: dict, limit: int = 10) -> list`
- Returns: `[{"name": str, "why": str}]`
- Pure AI, no topic awareness, no Reddit API calls, no subscriber info
- Caller: `cli_product.py:85` — `cmd_product_recommend_subreddits`

### `search_subreddits` (subreddits.py:31)
- Signature: `search_subreddits(query: str, limit: int = 10, client=None) -> list`
- Returns: `[{"display_name", "title", "subscribers", "description", "url"}]`
- Keyword-based Reddit API search — would miss semantically related subreddits

### `get_subreddit_info` (subreddits.py:36)
- Signature: `get_subreddit_info(name: str, client=None) -> dict`
- Returns: `_normalise_subreddit(data)` → `{display_name, title, subscribers, description, url}`
- Raises `KeyError` if API response has no "data" key
- Used to enrich candidates with real subscriber counts post-AI-generation

### `_normalise_subreddit` (subreddits.py:8)
- Returns: display_name, title, subscribers, description, url
- Does NOT expose self_promotion rules from raw Reddit data — Claude must estimate this

### Style CLI (cli_style.py)
- Already has learn/mimic/list/show with shared `_reddit_errors()` context manager
- Pattern for product resolution: args.product vs args.describe (lines 97-112)
- New `cmd_style_match` fits same file and pattern

### CLI wiring (cli.py:289-323)
- `style_sub` subparsers object defined at line 293
- Adding `match` parser requires: import `cmd_style_match` from cli_style, add subparser after show (line 322)

### Test infrastructure (test_writer.py)
- `make_anthropic_mock(text_response)` helper at line 11 — reuse for new tests
- Pattern: `patch("reddit_toolkit.writer._make_client", return_value=mock_client)`
- No existing tests for style match (doesn't exist yet)

---

## Design Approach

**Hybrid: AI generates semantically-aware candidates → Reddit API enriches with subscriber counts**

Why not pure AI: subscriber counts must be real, not hallucinated.
Why not search-first: keyword search misses semantically related subreddits (e.g. a DevOps tool wouldn't match "sysadmin" via keyword search of the product name).

**Step 1:** Claude receives `{product info + topic}` → returns `[{name, why, self_promo_tolerance, post_angle}]`
**Step 2:** CLI calls `get_subreddit_info(name)` for each → adds real subscriber count
**Step 3:** Gracefully skip subreddits that don't exist (KeyError from API)

---

## Changes by File

### 1. `reddit_toolkit/writer.py` — NEW function
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

### 2. `reddit_toolkit/cli_style.py` — NEW function `cmd_style_match`
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

    print(f"Finding best subreddits for: {args.topic or 'general post'}...")
    try:
        from .writer import match_subreddits_for_topic
        candidates = match_subreddits_for_topic(profile, topic=args.topic or "", limit=args.limit)
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Enrich with subscriber counts from Reddit API
    from .subreddits import get_subreddit_info
    enriched = []
    for c in candidates:
        try:
            info = get_subreddit_info(c["name"])
            c["subscribers"] = info["subscribers"]
        except Exception:
            c["subscribers"] = None
        enriched.append(c)

    # Display
    topic_label = args.topic or "general"
    print(f"\nTop {len(enriched)} subreddits for topic \"{topic_label}\":\n")
    for i, s in enumerate(enriched, 1):
        subs = f"{s['subscribers']:,}" if s.get("subscribers") else "unknown"
        print(f"  {i}. r/{s['name']} — {subs} subscribers")
        print(f"     Why: {s['why']}")
        print(f"     Self-promo: {s.get('self_promo_tolerance', '?')}")
        print(f"     Angle: {s.get('post_angle', '')}")
        print()

    # Next-step hints
    if enriched:
        top = enriched[0]["name"]
        print("Next steps:")
        print(f"  reddit-toolkit style learn --subreddit {top}")
        product_flag = f"--product {args.product}" if args.product else f'--describe "{profile.get("description", "")}"'
        topic_flag = f'--topic "{args.topic}"' if args.topic else ""
        print(f"  reddit-toolkit style mimic --subreddit {top} {product_flag} {topic_flag}")
```

### 3. `reddit_toolkit/cli.py` — add `match` subparser
Add import of `cmd_style_match` at line 290. Add subparser after `sshow_p.set_defaults` (line 323):
```python
sm2_p = style_sub.add_parser("match", help="Find subreddits that fit your product and topic")
product_group2 = sm2_p.add_mutually_exclusive_group(required=True)
product_group2.add_argument("--product", help="Saved product profile ID")
product_group2.add_argument("--describe", metavar="DESCRIPTION", help="Inline product description")
sm2_p.add_argument("--topic", "-t", default="", help="Post angle hint")
sm2_p.add_argument("--limit", "-n", type=int, default=5, help="Number of subreddits (default: 5)")
sm2_p.set_defaults(func=cmd_style_match)
```

### 4. `tests/test_writer.py` — new test class
```python
class TestMatchSubredditsForTopic:
    def test_returns_list(self):
        mock_client = make_anthropic_mock(
            '[{"name": "python", "why": "Active dev community", '
            '"self_promo_tolerance": "medium", "post_angle": "Share as a tool"}]'
        )
        profile = {"name": "MyApp", "description": "...", "target_audience": [], "key_features": []}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import match_subreddits_for_topic
                result = match_subreddits_for_topic(profile, topic="launch announcement")
        assert isinstance(result, list)
        assert result[0]["name"] == "python"
        assert "self_promo_tolerance" in result[0]

    def test_topic_in_prompt(self):
        mock_client = make_anthropic_mock('[{"name": "python", "why": "reason", "self_promo_tolerance": "low", "post_angle": "angle"}]')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import match_subreddits_for_topic
                match_subreddits_for_topic({}, topic="launch announcement", limit=3)
        messages = mock_client.messages.create.call_args.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "launch announcement" in prompt_text

    def test_parse_error_returns_empty_list(self):
        mock_client = make_anthropic_mock("not json")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                from reddit_toolkit.writer import match_subreddits_for_topic
                result = match_subreddits_for_topic({})
        assert result == []
```

---

## Acceptance Criteria

1. `reddit-toolkit style match --product <id> --topic "launch"` prints a ranked list with subscriber counts
2. `reddit-toolkit style match --describe "my tool" --topic "launch"` works without a saved profile
3. Each result shows: rank, subreddit name, subscriber count, why, self-promo tolerance, post angle
4. If a suggested subreddit doesn't exist on Reddit, it's skipped gracefully (no crash)
5. Output ends with copy-paste `style learn` + `style mimic` commands for top result
6. `--limit` controls number of results (default 5)
7. Parse error from Claude → empty result with no crash
8. `WriterConfigError` (no API key) → error message + exit 1

---

## Test Plan

- `TestMatchSubredditsForTopic` in test_writer.py: 3 tests (returns list, topic in prompt, parse error)
- No need for integration tests for CLI (pattern established by existing style tests)
- `get_subreddit_info` enrichment tested implicitly (mock the exception path)

---

## Non-Goals

- No caching of match results (results are fast/cheap, freshness matters for topic relevance)
- No auto-launching `style learn` after match (user picks which subreddit to pursue)
- No modification to existing `product recommend-subreddits` (different intent, keep separate)
