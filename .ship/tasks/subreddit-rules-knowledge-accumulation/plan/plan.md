# Plan: Subreddit Rules & Norms Knowledge Accumulation

## Task 1 — Create `rules_store.py` (mirrors style_store.py)

**File:** `reddit_toolkit/rules_store.py` (new)

```python
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .profile_store import slugify


class RulesNotFoundError(Exception):
    pass


def _data_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    return Path(base).expanduser()


def rules_dir() -> Path:
    d = _data_dir() / "rules"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(subreddit: str, data: dict) -> None:
    data["subreddit"] = subreddit.lower().strip().lstrip("r/")
    path = rules_dir() / f"{slugify(subreddit)}.rules.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load(subreddit: str) -> dict:
    path = rules_dir() / f"{slugify(subreddit)}.rules.json"
    if not path.exists():
        raise RulesNotFoundError(
            f"No rules profile for r/{subreddit}. "
            f"Run: reddit-toolkit rules learn --subreddit {subreddit}"
        )
    with open(path) as f:
        return json.load(f)


def is_stale_norms(data: dict, max_age_days: int = 7) -> bool:
    ts = data.get("norms_learned_at")
    if not ts:
        return True
    dt = datetime.fromisoformat(ts)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)


def is_stale_rules(data: dict, max_age_days: int = 30) -> bool:
    ts = data.get("rules_fetched_at")
    if not ts:
        return True
    dt = datetime.fromisoformat(ts)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)


def list_rules() -> list:
    return [json.loads(p.read_text()) for p in sorted(rules_dir().glob("*.rules.json"))]
```

**Test:** Import, save a dict, load it back, assert fields match.

---

## Task 2 — Create `rules_learner.py`

**File:** `reddit_toolkit/rules_learner.py` (new)

```python
import json
import os
import warnings
from datetime import datetime, timezone

from .reddit_client import RedditClient, RedditAPIError
from .style_learner import fetch_subreddit_corpus


class RulesInferenceError(Exception):
    pass


_NORMS_SYSTEM = (
    "You are a Reddit community analyst. Analyze these posts and infer the implicit "
    "community norms — what gets removed, what's welcome, unwritten rules. "
    "Return JSON only, no other text. "
    'Schema: {"tone_guidelines": str, "community_values": [str], '
    '"what_gets_removed": [str], "posting_checklist": [str], '
    '"safe_post_angles": [str], "link_rules": str}'
)


def fetch_official_rules(subreddit: str, client=None) -> list:
    """GET /r/{subreddit}/about/rules.json → list of {short_name, description, priority}."""
    c = client if client is not None else RedditClient()
    try:
        response = c.get(f"/r/{subreddit}/about/rules.json")
        rules = response.get("rules", [])
        return [
            {
                "short_name": r.get("short_name", ""),
                "description": r.get("description", ""),
                "priority": r.get("priority", 0),
            }
            for r in rules
        ]
    except (RedditAPIError, KeyError, Exception):
        return []


def infer_norms(subreddit: str, posts: list, ai_client=None) -> dict:
    """Call Claude with post corpus → inferred_norms dict. Raises RulesInferenceError on failure."""
    from .writer import _make_client as _make_writer_client
    client = ai_client or _make_writer_client()

    top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:100]
    lines = [
        f"SCORE:{p['score']} TITLE:{p['title']} BODY:{(p.get('selftext') or '')[:80]}"
        for p in top_posts
    ]
    user = f"Subreddit: r/{subreddit}\n\n" + "\n".join(lines)

    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=1024,
        system=_NORMS_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines_r = raw.splitlines()
        raw = "\n".join(lines_r[1:-1] if lines_r[-1].strip() == "```" else lines_r[1:])

    try:
        norms = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RulesInferenceError(
            f"AI returned invalid JSON for r/{subreddit} norm inference: {e}\n"
            "Try: reddit-toolkit rules learn --force --subreddit " + subreddit
        ) from e

    required = {"tone_guidelines", "community_values", "what_gets_removed",
                "posting_checklist", "safe_post_angles", "link_rules"}
    missing = required - set(norms.keys())
    if missing:
        raise RulesInferenceError(
            f"AI response missing required keys: {missing}. "
            "Try: reddit-toolkit rules learn --force --subreddit " + subreddit
        )

    tokens = getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0)
    return norms, tokens


def learn_rules(subreddit: str, posts: list = None, reddit_client=None, ai_client=None) -> dict:
    """Orchestrate: fetch official rules + infer norms. Returns full rules dict."""
    now = datetime.now(timezone.utc).isoformat()

    official = fetch_official_rules(subreddit, client=reddit_client)
    rules_fetched_at = now

    if posts is None:
        posts = fetch_subreddit_corpus(subreddit, pages=5, client=reddit_client)

    norms, tokens = infer_norms(subreddit, posts, ai_client=ai_client)
    norms_learned_at = datetime.now(timezone.utc).isoformat()

    return {
        "subreddit": subreddit.lower(),
        "rules_fetched_at": rules_fetched_at,
        "norms_learned_at": norms_learned_at,
        "official_rules": official,
        "inferred_norms": norms,
        "inference_metadata": {
            "posts_analyzed": len(posts),
            "norms_model_used": os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
            "inference_token_cost": tokens,
        },
    }
```

**Test:** Call `fetch_official_rules("python")` against live Reddit API, assert returns list. Call `learn_rules` with mock posts, assert required keys present.

---

## Task 3 — Patch `writer.py`: add `rules` param to `generate_mimic_post`

**File:** `reddit_toolkit/writer.py`

At `generate_mimic_post` signature (line 341-342), change:
```python
def generate_mimic_post(
    subreddit: str, style: dict, profile: dict, topic: str = ""
) -> dict:
```
to:
```python
def generate_mimic_post(
    subreddit: str, style: dict, profile: dict, topic: str = "", rules: dict = None
) -> dict:
```

In the system prompt construction (after line 371, the `taboo_topics` line), add:
```python
        if rules:
            official = rules.get("official_rules", [])
            if official:
                rules_text = "\n".join(
                    f"- {r['short_name']}: {r.get('description','')[:200]}"
                    for r in official[:5]
                )
                system += f"\n\nOfficial subreddit rules (must not violate):\n{rules_text}"
            checklist = rules.get("inferred_norms", {}).get("posting_checklist", [])
            if checklist:
                system += "\n\nPosting checklist:\n" + "\n".join(f"- {c}" for c in checklist)
            what_removed = rules.get("inferred_norms", {}).get("what_gets_removed", [])
            if what_removed:
                system += "\n\nWhat gets removed in this sub:\n" + "\n".join(f"- {c}" for c in what_removed)
```

Also patch `write_post_body` (line 68) signature with `rules=None` and inject same way.

**Test:** Call `generate_mimic_post` with `rules={"official_rules": [{"short_name": "No spam", "description": "test"}], "inferred_norms": {"posting_checklist": ["Lead with value"]}}` and assert "No spam" appears in generated system prompt (mock the client).

---

## Task 4 — Patch `cli_style.py`: auto-learn rules in `_learn_subreddit` + load in `cmd_style_mimic`

**File:** `reddit_toolkit/cli_style.py`

In `_learn_subreddit` (line 30-40), after `save_style(subreddit, cache)` (line 39), add:
```python
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
```

Note: `posts` is already in scope at `_learn_subreddit` (returned from `fetch_subreddit_corpus` via `with _reddit_errors()` block). Verify: cli_style.py:32-34 shows `posts = fetch_subreddit_corpus(...)` — yes, in scope.

In `cmd_style_mimic` (line 80), at line 98 — immediately after the `except StyleNotFoundError` block closes (line 97) and before the `# Resolve product info` comment (line 99), add:
```python
    # Load rules if cached (non-fatal if missing)
    rules_data = None
    try:
        from .rules_store import load as load_rules, RulesNotFoundError
        rules_data = load_rules(args.subreddit)
    except Exception:
        pass
```

Change `generate_mimic_post` call (line 119-124) to pass `rules=rules_data`.

---

## Task 5 — Patch `cli_scan.py`: best-effort rules fetch before scan

**File:** `reddit_toolkit/cli_scan.py`

In `cmd_scan_run` (line 15), after loading `profile` (line 17-20), add:
```python
    # Best-effort: ensure rules are cached for each target subreddit
    from .rules_store import load as load_rules, is_stale_norms, RulesNotFoundError
    from .rules_learner import learn_rules, RulesInferenceError
    from .rules_store import save as save_rules
    for sub in profile.get("subreddits", []):
        sub_name = sub["name"] if isinstance(sub, dict) else sub
        try:
            existing = load_rules(sub_name)
            if not is_stale_norms(existing):
                continue
        except RulesNotFoundError:
            pass
        try:
            rules_data = learn_rules(sub_name)
            save_rules(sub_name, rules_data)
        except Exception:
            pass  # non-fatal: scan proceeds without rules
```

---

## Task 6 — Create `cli_rules.py`

**File:** `reddit_toolkit/cli_rules.py` (new)

```python
import sys

from .rules_store import load, list_rules, is_stale_norms, is_stale_rules, RulesNotFoundError
from .rules_learner import learn_rules, RulesInferenceError
from .rules_store import save


def cmd_rules_learn(args):
    try:
        existing = load(args.subreddit)
        if not args.force and not is_stale_norms(existing):
            print(f"Rules for r/{args.subreddit} are fresh. Use --force to re-learn.")
            return
    except RulesNotFoundError:
        pass

    print(f"Fetching official rules for r/{args.subreddit}...")
    try:
        data = learn_rules(args.subreddit)
        save(args.subreddit, data)
    except RulesInferenceError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    n_official = len(data.get("official_rules", []))
    norms = data.get("inferred_norms", {})
    checklist = norms.get("posting_checklist", [])
    print(f"\nRules profile saved for r/{args.subreddit}.")
    print(f"  Official rules: {n_official}")
    print(f"  Tone: {norms.get('tone_guidelines', 'N/A')[:80]}")
    print(f"  Posting checklist: {len(checklist)} items")


def cmd_rules_show(args):
    import json
    try:
        data = load(args.subreddit)
    except RulesNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, indent=2))


def cmd_rules_list(args):
    all_rules = list_rules()
    if not all_rules:
        print("No rules profiles cached. Run: reddit-toolkit rules learn --subreddit <name>")
        return
    for r in all_rules:
        stale = " [STALE]" if is_stale_norms(r) else ""
        learned = r.get("norms_learned_at", "")[:10]
        n = len(r.get("official_rules", []))
        print(f"  r/{r.get('subreddit', '?')} — {n} official rules — learned {learned}{stale}")
```

---

## Task 7 — Register `rules` subcommand in `cli.py`

**File:** `reddit_toolkit/cli.py`

After line 298 (end of `notion` block), add:
```python
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
```

---

## Execution order

Tasks 1 and 2 are independent — can run in parallel.
Task 3 depends on nothing.
Task 4 depends on Tasks 1, 2, 3.
Task 5 depends on Tasks 1, 2.
Task 6 depends on Tasks 1, 2.
Task 7 depends on Task 6.

Wave 1: Tasks 1, 2, 3
Wave 2: Tasks 4, 5, 6
Wave 3: Task 7

---

## Smoke test sequence

```bash
# 1. Learn rules for a subreddit
ANTHROPIC_API_KEY=... NOTION_TOKEN=... reddit-toolkit rules learn --subreddit ClaudeAI

# 2. Show them
reddit-toolkit rules show --subreddit ClaudeAI

# 3. List all cached
reddit-toolkit rules list

# 4. Mimic now uses rules automatically
reddit-toolkit style mimic --subreddit ClaudeAI --product ship --topic "launch"

# 5. Style learn auto-learns rules going forward
reddit-toolkit style learn --subreddit cursor
```
