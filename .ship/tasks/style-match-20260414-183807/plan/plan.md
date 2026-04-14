# Plan: `style match` — Topic-Aware Subreddit Matching

task_id: style-match-20260414-183807

## Stories

### Story 1: Add `match_subreddits_for_topic` to writer.py + tests

**Files:** `reddit_toolkit/writer.py`, `tests/test_writer.py`

**Steps:**

- [ ] Open `reddit_toolkit/writer.py`. After `recommend_subreddits` function (line 159), add:

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

- [ ] Open `tests/test_writer.py`. Update top-level imports (lines 4-8) to add `match_subreddits_for_topic`. The full updated import block:

```python
from reddit_toolkit.writer import (
    generate_post_title, write_post_body, generate_comment, WriterConfigError,
    score_post_for_product, generate_opportunity_draft,
    extract_profile_from_text, recommend_subreddits,
    analyze_subreddit_style, generate_mimic_post,
    match_subreddits_for_topic,
)
```

- [ ] Add after the last test class in `tests/test_writer.py`:

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

- [ ] Run tests: `python3 -m pytest tests/test_writer.py -v`
- [ ] Verify 4 new tests pass, all existing tests still pass
- [ ] Commit: `feat(writer): add match_subreddits_for_topic`

---

### Story 2: Add `cmd_style_match` to cli_style.py + wire into cli.py

**Files:** `reddit_toolkit/cli_style.py`, `reddit_toolkit/cli.py`

**Depends on:** Story 1 (imports `match_subreddits_for_topic`)

**Steps:**

- [ ] Open `reddit_toolkit/cli_style.py`. Update the writer import (currently line 12):

```python
# Before:
from .writer import analyze_subreddit_style, generate_mimic_post, WriterConfigError
# After:
from .writer import analyze_subreddit_style, generate_mimic_post, match_subreddits_for_topic, WriterConfigError
```

- [ ] Add to imports at the top of `cli_style.py` (after line 12, add a new import line):

```python
from .subreddits import get_subreddit_info
```

- [ ] Add the following function after `cmd_style_show` (end of file):

```python
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
```

- [ ] Open `reddit_toolkit/cli.py`. Update the style import line (currently line 290):

```python
# Before:
from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show
# After:
from .cli_style import cmd_style_learn, cmd_style_mimic, cmd_style_list, cmd_style_show, cmd_style_match
```

- [ ] In `build_parser()`, after `sshow_p.set_defaults(func=cmd_style_show)` (line 323), add:

```python
    # style match
    smatch_p = style_sub.add_parser("match", help="Find subreddits that fit your product and topic")
    product_group_m = smatch_p.add_mutually_exclusive_group(required=True)
    product_group_m.add_argument("--product", help="Saved product profile ID")
    product_group_m.add_argument("--describe", metavar="DESCRIPTION",
                                  help="Inline product description (no profile needed)")
    smatch_p.add_argument("--topic", "-t", default="", help="Post angle hint (e.g. 'launch announcement')")
    smatch_p.add_argument("--limit", "-n", type=int, default=5, help="Number of subreddits (default: 5)")
    smatch_p.set_defaults(func=cmd_style_match)
```

- [ ] Run tests: `python3 -m pytest -v`
- [ ] Verify all tests pass
- [ ] Run smoke test: `python3 -m reddit_toolkit.cli style --help` (should show `match` in subcommand list)
- [ ] Run smoke test: `python3 -m reddit_toolkit.cli style match --help` (should show `--product`, `--describe`, `--topic`, `--limit`)
- [ ] Commit: `feat(style): add style match command`

---

## Dependency Wave

```
Wave 1 (parallel): Story 1 only (writer.py + tests)
Wave 2 (sequential): Story 2 (depends on Story 1 for match_subreddits_for_topic import)
```

Story 2 imports `match_subreddits_for_topic` from `writer.py` — must run after Story 1 commits.

## Test Command

```bash
python3 -m pytest -v
```

## Acceptance Verification

After both stories complete, verify:
```bash
python3 -m reddit_toolkit.cli style match --help
# → shows match subparser with --product/--describe, --topic, --limit

python3 -m pytest tests/test_writer.py -v -k "TestMatchSubredditsForTopic"
# → 4 tests pass
```
