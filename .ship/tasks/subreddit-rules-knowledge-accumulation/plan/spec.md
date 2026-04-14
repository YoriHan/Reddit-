# Spec: Subreddit Rules & Norms Knowledge Accumulation

HEAD SHA: (standalone design)
Scope: Broad — 2 new files, 4 existing files modified

---

## Problem

`generate_mimic_post` (writer.py:341) uses a style dict that captures *tone and vocabulary* but not *what's actually allowed*. The style dict does include `taboo_topics` and `self_promotion_tolerance` (writer.py:302-307) inferred from post corpus, but:

1. Official subreddit rules are never fetched — violations can trigger removal
2. Inferred norms (what gets removed, karma gates, link rules) aren't persisted — re-derived every time from a writing style perspective only
3. No posting history — the tool doesn't know whether a subreddit has already been posted to

---

## New Architecture

### New files

| File | Role |
|------|------|
| `reddit_toolkit/rules_store.py` | Read/write/list rules JSON files — mirrors style_store.py exactly |
| `reddit_toolkit/rules_learner.py` | Fetch official rules from Reddit API + AI norm inference |
| `reddit_toolkit/cli_rules.py` | CLI handlers: `rules learn`, `rules show`, `rules list` |

### Modified files

| File | Change |
|------|--------|
| `reddit_toolkit/writer.py` | `generate_mimic_post` gets optional `rules=None` param; injects rules into prompt |
| `reddit_toolkit/cli_style.py` | `_learn_subreddit` auto-fetches rules after learning style; `cmd_style_mimic` loads + passes rules |
| `reddit_toolkit/cli_scan.py` | `cmd_scan_run` auto-fetches rules for each subreddit before scoring |
| `reddit_toolkit/cli.py` | Register `rules` top-level subcommand group |

---

## Data Schema

Path: `~/.reddit-toolkit/rules/{slugify(subreddit)}.rules.json`

`slugify` already imported from `profile_store` in style_store.py:6 — reuse.

```json
{
  "subreddit": "ClaudeAI",
  "learned_at": "2026-04-14T14:00:00+00:00",
  "official_rules": [
    {
      "short_name": "No spam",
      "description": "Full rule text from sidebar",
      "priority": 1
    }
  ],
  "inferred_norms": {
    "self_promo_hard_limit": "Must be established community member first",
    "what_gets_removed": ["promotional links without context", "repeated posts"],
    "safe_post_angles": ["genuine experience sharing", "questions", "show HN style"],
    "link_rules": "Direct product links only if discussed, not as the headline",
    "karma_or_age_gate": "none observed",
    "flair_required": false,
    "optimal_post_length": "medium (200-500 words)",
    "posting_checklist": [
      "Lead with the experience, not the product",
      "No affiliate links",
      "Don't post same content across multiple subreddits same day"
    ]
  }
}
```

TTL: 30 days (rules rarely change; style uses 7 days at style_store.py:43)

---

## Reddit API Endpoint

Official rules: `GET /r/{subreddit}/about/rules.json`

Response format:
```json
{
  "rules": [
    {
      "short_name": "...",
      "description": "...",
      "priority": 0,
      "created_utc": 0.0
    }
  ],
  "site_rules": ["..."],
  "site_rules_flow": [...]
}
```

Uses existing `RedditClient.get()` (reddit_client.py:14) — no auth needed, public endpoint.

---

## AI Norm Inference

**Input**: official rules text + top-25 post titles/bodies from `fetch_subreddit_corpus` (style_learner.py:7) — already available when `style learn` runs.

**Prompt**: Ask Claude to infer practical norms not captured in official rules, returning the `inferred_norms` JSON dict above.

**Claude call pattern**: mirrors `analyze_subreddit_style` (writer.py:275) — uses `_make_client()` + `client.messages.create()`, returns parsed JSON, falls back on parse error.

**Max tokens**: 1024 (norms are shorter than style analysis)

**Model**: `os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5")` — same as writer.py:23

---

## Integration Points

### 1. `rules_store.py` (new)

Mirror of `style_store.py` verbatim, with:
- `rules_dir()` → `~/.reddit-toolkit/rules/`
- `save(subreddit, data)` — writes `learned_at`, subreddit slug
- `load(subreddit)` → raises `RulesNotFoundError` if missing
- `is_stale(data, max_age_days=30)` — 30-day TTL
- `list_rules()` → all cached rule profiles

### 2. `rules_learner.py` (new)

```python
def fetch_official_rules(subreddit: str, client=None) -> list:
    """GET /r/{subreddit}/about/rules.json → list of {short_name, description, priority}"""

def infer_norms(subreddit: str, official_rules: list, posts: list, ai_client=None) -> dict:
    """Call Claude with rules + post sample → inferred_norms dict"""

def learn_rules(subreddit: str, posts: list = None, reddit_client=None, ai_client=None) -> dict:
    """Orchestrate: fetch rules + infer norms. posts optional (fetches 5-page corpus if None)."""
```

`posts` parameter allows `_learn_subreddit` in cli_style.py to pass already-fetched corpus — avoids double network call.

### 3. `writer.py` — `generate_mimic_post` signature change

```python
def generate_mimic_post(
    subreddit: str, style: dict, profile: dict, topic: str = "", rules: dict = None
) -> dict:
```

In the system prompt (writer.py:359), after the existing "Topics to avoid" line (line 371), add:

```python
if rules:
    official = "\n".join(
        f"- {r['short_name']}: {r['description'][:200]}"
        for r in rules.get("official_rules", [])
    )
    checklist = "\n".join(f"- {c}" for c in rules.get("inferred_norms", {}).get("posting_checklist", []))
    system += f"\n\nOfficial subreddit rules (must not violate):\n{official}"
    if checklist:
        system += f"\n\nPosting checklist:\n{checklist}"
```

Backward-compatible: `rules=None` → no change in behavior.

### 4. `cli_style.py` — `_learn_subreddit` (line 30)

After `save_style(subreddit, cache)` (line 39), add:
```python
from .rules_learner import learn_rules
from .rules_store import save as save_rules
rules_data = learn_rules(subreddit, posts=posts, ai_client=_make_client())
save_rules(subreddit, rules_data)
```

`posts` is already fetched at this point — pass it to avoid re-fetching.

In `cmd_style_mimic` (line 80), after loading `cached` style, add:
```python
from .rules_store import load as load_rules, RulesNotFoundError
try:
    rules_data = load_rules(args.subreddit)
except RulesNotFoundError:
    rules_data = None
```

Pass `rules=rules_data` to `generate_mimic_post` call at line 119.

### 5. `cli_scan.py` — `cmd_scan_run`

After loading profile (line 17), before calling `run_scan`, add a best-effort rules fetch for each subreddit in the profile:
```python
from .rules_learner import learn_rules
from .rules_store import save as save_rules, load as load_rules, is_stale, RulesNotFoundError
for sub in profile.get("subreddits", []):
    name = sub["name"] if isinstance(sub, dict) else sub
    try:
        existing = load_rules(name)
        if is_stale(existing, max_age_days=30):
            raise RulesNotFoundError()
    except RulesNotFoundError:
        try:
            rules_data = learn_rules(name)
            save_rules(name, rules_data)
        except Exception:
            pass  # non-fatal
```

Note: `run_scan` in scanner.py doesn't call `generate_mimic_post` directly — it calls `generate_opportunity_draft` (scanner.py, via writer.py). That function should also receive rules. This requires a small scanner.py change (pass rules dict when calling the draft generator). **This is a secondary integration** — do in same PR but lower priority.

### 6. `cli_rules.py` (new) — CLI handlers

```python
def cmd_rules_learn(args):   # reddit-toolkit rules learn --subreddit X [--force]
def cmd_rules_show(args):    # reddit-toolkit rules show --subreddit X
def cmd_rules_list(args):    # reddit-toolkit rules list
```

### 7. `cli.py` — Register `rules` top-level subcommand

After the `notion` block (line 298), add:
```python
from .cli_rules import cmd_rules_learn, cmd_rules_show, cmd_rules_list
rules_parser = subparsers.add_parser("rules", help="Manage subreddit rules and norms")
rules_sub = rules_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

rl_p = rules_sub.add_parser("learn", help="Fetch and analyze subreddit rules")
rl_p.add_argument("--subreddit", "-s", required=True)
rl_p.add_argument("--force", action="store_true")
rl_p.set_defaults(func=cmd_rules_learn)

rs_p = rules_sub.add_parser("show", help="Show cached rules for a subreddit")
rs_p.add_argument("--subreddit", "-s", required=True)
rs_p.set_defaults(func=cmd_rules_show)

rlist_p = rules_sub.add_parser("list", help="List all cached rule profiles")
rlist_p.set_defaults(func=cmd_rules_list)
```

---

## CLI Output Format

### `rules learn --subreddit ClaudeAI`
```
Fetching rules for r/ClaudeAI...
  Official rules: 5 found
Inferring community norms with AI...
Rules profile saved for r/ClaudeAI.
  Official rules: No spam, No self-promotion without participation, ...
  Key norms: Lead with experience not product, No affiliate links
  Posting checklist: 4 items
```

### `rules show --subreddit ClaudeAI`
Pretty-prints the JSON (same as `style show`).

### `rules list`
```
  r/ClaudeAI — 5 rules — learned 2026-04-14
  r/cursor   — 3 rules — learned 2026-04-14 [STALE]
```

---

## Risks & Edge Cases

| Risk | Mitigation |
|------|-----------|
| Subreddit has no public rules | `official_rules: []`, infer norms from posts only |
| Reddit API rate limit | RedditClient already sleeps 1s between calls (reddit_client.py:30) |
| AI norm inference fails (parse error) | Fall back to `{"self_promo_hard_limit": "unknown", "posting_checklist": []}` |
| `_learn_subreddit` corpus not passed | `learn_rules` fetches its own 5-page corpus — slower but safe |
| Scanner subreddit list format | `sub` can be `str` or `dict` — handle both with `sub["name"] if isinstance(sub, dict) else sub` |
| Breaking change to `generate_mimic_post` signature | `rules=None` default — fully backward-compatible |
