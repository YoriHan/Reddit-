# Peer Spec: `style match` — Topic-Aware Subreddit Matching

WARNING: Second spec was self-generated, not independent

---

## Key Differences / Additions vs Host Spec

### 1. Import placement for `get_subreddit_info`

Host spec places `from .subreddits import get_subreddit_info` inline inside `cmd_style_match`.
This is inconsistent with the file's existing pattern — all imports are top-level in `cli_style.py:1-13`.
**Fix: add `get_subreddit_info` to the top-level imports of `cli_style.py`.**

Evidence: `cli_style.py:8` — `from .profile_store import load as load_profile, ProfileNotFoundError`; `cli_style.py:10` — `from .style_store import load as load_style, list_styles, StyleNotFoundError, is_stale, save as save_style` — all are top-level.

### 2. Exception handling during enrichment is too broad

Host spec uses `except Exception` to swallow enrichment failures. `get_subreddit_info` (subreddits.py:36-41) raises:
- `KeyError` when Reddit returns a response without `data`
- `RedditAPIError` (reddit_client.py:6) on HTTP errors
- `requests.exceptions.ConnectionError` on network failures

Using `except Exception` would also swallow programming errors (AttributeError, NameError, etc.), hiding bugs. **Fix: catch `(KeyError, RedditAPIError, requests.exceptions.ConnectionError)` specifically.**

### 3. `match_subreddits_for_topic` should use `_call_claude()` not `client.messages.create` directly

Host spec's function body calls `_call_claude(client, system, user)` which already uses the 1024-token default — this is correct and consistent with the existing pattern (`writer.py:21-28` — `_call_claude` uses 1024 tokens). The output is a compact JSON array with 5 items, well within 1024 tokens.

No change needed — host spec was already correct on this. Just confirming.

### 4. Missing test: topic is optional

Host spec has 3 tests but doesn't test `match_subreddits_for_topic({})` with no topic — confirming empty-string topic produces valid call. **Add 4th test: no topic (empty string default) works.**

### 5. Missing: `match_subreddits_for_topic` import in `test_writer.py`

`test_writer.py:4-8` imports from writer explicitly. Must add `match_subreddits_for_topic` to the import list, otherwise the class-level `from reddit_toolkit.writer import match_subreddits_for_topic` inside each test method is redundant and inconsistent.

**Fix: Add to top-level import in test_writer.py:**
```python
from reddit_toolkit.writer import (
    ...,
    match_subreddits_for_topic,
)
```

---

## Agreement with Host Spec

- Command location: `style match` under style namespace ✓
- Hybrid approach (AI candidates + Reddit API enrichment) ✓
- Output schema: name, why, self_promo_tolerance, post_angle, subscribers ✓
- `--product` / `--describe` mutual exclusion ✓
- Graceful skip for non-existent subreddits ✓
- Next-step hints printed at end ✓
- No caching ✓
- Files: writer.py, cli_style.py, cli.py, tests/test_writer.py ✓
