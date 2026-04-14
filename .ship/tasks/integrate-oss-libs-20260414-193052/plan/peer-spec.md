# Peer Spec: Integrate PRAW, newspaper3k, rich, schedule

WARNING: Second spec was self-generated, not independent.

---

## Key Differences / Additions vs Host Spec

### 1. PRAW .get() mapping is incomplete for post fields

Host spec says `PRAWClient.get()` maps praw `Submission` objects to the same dict schema as the anonymous API. However, the existing `content.py:_normalise_post()` requires these fields from `data`:
- `title`, `score`, `url`, `subreddit`, `author`, `num_comments`, `permalink`, `created_utc`, `selftext`

PRAW `Submission` has all these as direct attributes (`.title`, `.score`, `.url`, etc.) but `.author` can be `None` (deleted accounts). Host spec doesn't handle this.

**Fix: `PRAWClient.get()` must serialize `str(sub.author) if sub.author else "[deleted]"` for author field.**

Also: `created_utc` in PRAW is already a float — no conversion needed.

### 2. rich display.py — test_display.py needs complete rewrite of assertions

Host spec says "update assertions to match new format strings." But `test_display.py` currently checks:
- `"Title" in out` (column header)
- `"python" in out` (subreddit name in list)
- `"1,468,454" in out` (subscriber count)
- `"Test post title" in out` (post title)

These will still be present in a `rich.table.Table` render to a `Console(file=StringIO())` because rich renders table cell content as plain text in non-TTY mode (when `force_terminal=False`). So assertions checking for content strings should still pass.

**Clarification: `Console(file=StringIO())` does NOT need `force_terminal=True` — rich auto-detects non-TTY and uses plain-text rendering. Tests can check for the same content strings.**

This means test_display.py needs only:
1. Change `patch("sys.stdout", buf)` → pass `console=Console(file=buf)` to the function
2. Keep the same string containment assertions

### 3. newspaper3k import name is `newspaper` not `newspaper3k`

Host spec references `newspaper3k` — the PyPI package name. The import in Python is `import newspaper` (not `import newspaper3k`). This is a common confusion.

`extractor.py` should use: `import newspaper; article = newspaper.Article(url)`

### 4. schedule daemon — missing import of `load_profile` in cli_scan.py

Host spec says `cmd_scan_daemon` calls `run_scan(profile, ...)`. But `profile` must be loaded first. `cli_scan.py` already imports `load_profile` from `.profile_store` (used by `cmd_scan_run` at line 22). No new import needed — just call `load_profile(args.product)` the same way `cmd_scan_run` does.

**Add: explicit error handling if profile not found — `except ProfileNotFoundError as e: print(f"Error: {e}"); sys.exit(1)`**

### 5. PRAW read-only mode credentials

Host spec doesn't specify the `user_agent` string for PRAW's `praw.Reddit()`. PRAW requires a non-empty `user_agent`. Use: `user_agent="reddit-toolkit/1.0 by user"` hardcoded, or read from env `REDDIT_USER_AGENT` with that fallback.

### 6. pyproject.toml — newspaper3k has Python 3.12+ compatibility issues

newspaper3k (the old package) is unmaintained and may fail on Python 3.12+. Consider `newspaper4k` instead (fork with Python 3.12 support, same API). The import is still `import newspaper`.

**Check pyproject.toml python_requires. If 3.12+, use `newspaper4k` in pyproject.toml deps, import still works as `import newspaper`.**

---

## Agreement with Host Spec

- PRAW as optional enhancement (not replacement) ✓
- PRAWClient with same .get() interface ✓
- `console=None` injection for rich ✓
- newspaper3k adds `read_url()` to extractor.py ✓
- `--from-url` in cli_product.py ✓
- schedule daemon with interval parsing ✓
- 4-wave parallel structure (Wave 1: newspaper3k/rich/schedule parallel, Wave 2: PRAW sequential) ✓
