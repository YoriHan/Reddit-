# Spec: Integrate PRAW, newspaper3k (newspaper4k), rich, schedule

HEAD SHA: cd48827f5ed027963cd3c22dd6c1d92b4e83d516

---

## Problem / Motivation

Four capability gaps in the Reddit toolkit, each addressed by an OSS library:

1. **PRAW** — Style learning fetches only post titles/scores; PRAW enables optional comment corpus enrichment for richer style analysis
2. **newspaper4k** — Product creation needs URL ingestion; currently only `--from-file`, `--from-dir`, `--description`
3. **rich** — Terminal output is plain text; users navigating scan results, style matches, subreddit lists deserve formatted tables
4. **schedule** — `scan setup-cron` prints a crontab line; users want an in-process daemon without manual crontab setup

---

## Design Approach

### PRAW — Optional Enhancement, Not Replacement

**Critical constraint:** `test_style_learner.py`, `test_content.py`, `test_subreddits.py` mock `client.get()` via `MagicMock()`. Replacing `RedditClient` with PRAW would break 20+ tests.

**Solution:** Add `reddit_toolkit/praw_client.py` with `PRAWClient`:
- Same `.get(path, params) -> dict` interface — serializes PRAW objects to the same dict schema as the anonymous API
- New `.fetch_comments_for_post(permalink: str, limit: int = 20) -> list[str]` method
- Used **only** in `cmd_style_learn` when `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` env vars set
- Falls back to `RedditClient()` silently otherwise

**PRAW read-only auth:** `praw.Reddit(client_id, client_secret, user_agent)` — no user login required.

**Serialization details for PRAWClient.get():**
- Path `/r/{sub}/top.json?t=all` → `subreddit.top(time_filter="all", limit=limit, params={"after": after})`
- Path `/r/{sub}/hot.json` → `subreddit.hot(limit=limit)`
- For each `Submission`: `author = str(sub.author) if sub.author else "[deleted]"`
- Returns: `{"data": {"after": None, "children": [{"kind": "t3", "data": {all fields}}]}}`
- Note: PRAW listing generators don't expose `after` cursor — return `None` always; the paginator in `style_learner.py` will stop on empty batch

**Comment enrichment in `style_learner.py`:**
- After fetching posts, if `isinstance(client, PRAWClient)`:
  - For top 5 posts, call `client.fetch_comments_for_post(post["permalink"], limit=10)`
  - Append comment strings to `corpus` list as additional text samples
- If `fetch_comments_for_post` raises any exception, log warning and skip

**user_agent:** `os.environ.get("REDDIT_USER_AGENT", "reddit-toolkit/1.0")`

### newspaper4k — URL Ingestion

- `extractor.py`: add `read_url(url: str) -> str`
  - `import newspaper`
  - `article = newspaper.Article(url); article.download(); article.parse()`
  - If `article.text.strip()` is empty: raise `ValueError(f"No article text found at {url}")`
  - Returns `article.text`
- `cli_product.py`: add `--from-url URL` argument; add `elif args.from_url: raw_text = read_url(args.from_url)` branch
- `tests/test_extractor.py`: add `TestReadUrl` class with mock `newspaper.Article`
- pyproject.toml: add `"newspaper4k>=0.9.3"` (import is `import newspaper`)

### rich — Formatted Terminal Output

- Rewrite `display.py` using `rich.console.Console`, `rich.table.Table`, `rich.panel.Panel`
- **Injectable console:** all 3 functions gain `console=None` parameter
  - Default: `if console is None: console = Console()`
  - Tests: pass `Console(file=buf, force_terminal=False)` — renders plain text, same string-containment assertions work

**New output format:**
- `print_posts(posts, verbose=False, console=None)`:
  - `Table` with columns: `#` (right, dim), `Title` (max 60), `Score` (right), `Comments` (right), `Subreddit`
  - If `verbose`: add `URL` and `Text Preview` (max 100) columns
- `print_subreddits(subs, console=None)`:
  - `Table` with columns: `#` (right, dim), `Subreddit`, `Subscribers` (right), `Description` (max 50)
- `print_text(label, content, console=None)`:
  - `Panel(content, title=label)`

**test_display.py changes:**
- Remove `patch("sys.stdout", buf)` pattern
- Replace with `buf = StringIO(); console = Console(file=buf, force_terminal=False); print_posts(posts, console=console)`
- Keep same string-containment assertions (content text survives rich non-TTY render)

### schedule — Scan Daemon

- `cli_scan.py`: add `cmd_scan_daemon(args)`
  - Parse `args.interval` with regex `^(\d+)(h|m|d)$`; invalid format → print error + exit 1
  - `load(args.product)` with `ProfileNotFoundError` handling (same pattern as `cmd_scan_run:12-16`)
  - Define `job()` closure: calls `run_scan(profile, dry_run=False, top_n=10, threshold=7.0)`
  - `schedule.every(N).hours/minutes/days.do(job)` (h→hours, m→minutes, d→days)
  - Print: `"Daemon started. Scanning every {args.interval}. Ctrl+C to stop."`
  - `while True: schedule.run_pending(); time.sleep(60)`
  - `except KeyboardInterrupt: print("\nDaemon stopped."); sys.exit(0)`

- `cli.py`: add `scan daemon` subparser
  - `--product` (required)
  - `--interval`, `-i`, default `"8h"`, help `"Scan interval (e.g. 8h, 30m, 1d)"`
  - `sdaemon_p.set_defaults(func=cmd_scan_daemon)`

---

## Files Changed

| File | Change |
|------|--------|
| `reddit_toolkit/praw_client.py` | NEW |
| `reddit_toolkit/style_learner.py` | UPDATE — comment enrichment if PRAWClient |
| `reddit_toolkit/cli_style.py` | UPDATE — use PRAWClient when env vars set |
| `reddit_toolkit/extractor.py` | UPDATE — add read_url() |
| `reddit_toolkit/cli_product.py` | UPDATE — add --from-url |
| `reddit_toolkit/display.py` | REWRITE — rich tables + injectable console |
| `reddit_toolkit/cli_scan.py` | UPDATE — add cmd_scan_daemon() |
| `reddit_toolkit/cli.py` | UPDATE — add scan daemon subparser |
| `pyproject.toml` | UPDATE — add praw, newspaper4k, rich, schedule |
| `tests/test_praw_client.py` | NEW |
| `tests/test_extractor.py` | UPDATE — add TestReadUrl |
| `tests/test_display.py` | UPDATE — Console injection |

---

## Acceptance Criteria

1. `reddit-toolkit style learn --subreddit python` — if `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` set, fetches posts + top 5 post comments; otherwise fetches posts only (no crash)
2. `reddit-toolkit product create --from-url https://example.com` — extracts article text and creates profile
3. `reddit-toolkit scan list` (or any command that calls `print_posts`/`print_subreddits`) — output renders in rich table format
4. `reddit-toolkit scan daemon --product myapp --interval 8h` — prints "Daemon started..." and loops; Ctrl+C exits cleanly
5. `reddit-toolkit scan daemon --product myapp --interval bad` — prints error + exits 1
6. All 96 existing tests continue to pass
7. 4+ new tests for newspaper4k, 3+ for rich injection, 3+ for PRAWClient, 2+ for daemon interval parsing

---

## Non-Goals

- No replacement of RedditClient
- No auth UI for PRAW credentials
- No schedule job persistence
- No newspaper4k caching
- No rich formatting for style-specific outputs (style learn corpus, style show analysis)
