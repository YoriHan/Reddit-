# Host Spec: Integrate PRAW, newspaper3k, rich, schedule

HEAD SHA: cd48827f5ed027963cd3c22dd6c1d92b4e83d516

---

## Problem / Motivation

The toolkit has 4 capability gaps addressable by existing OSS libraries:

1. **Comment-blind style learning** — `style_learner.py` fetches only posts; PRAW can add comments to enrich corpus
2. **URL-only product creation** — `cli_product.py` accepts `--from-file`/`--from-dir`/`--description`; no URL ingestion
3. **Plain-text output** — `display.py` uses `print()` — no tables, no color
4. **Manual cron setup** — `cmd_scan_setup_cron` only prints a crontab line; no in-process daemon

---

## Investigation Findings

### reddit_client.py (36 lines)
- `RedditClient.get(path, params) -> dict`
- Anonymous HTTP GET to `https://www.reddit.com`
- Raises `RedditAPIError` on non-200

### content.py / subreddits.py / style_learner.py
- All accept `client=None` → `_client(client)` resolves to `RedditClient()`
- Interface: `client.get(path, params) -> dict`
- `test_style_learner.py`: `MagicMock()` with `client.get.side_effect = [responses]`
- `test_content.py` / `test_subreddits.py`: `MagicMock()` with `client.get.return_value = {...}`
- **PRAW must not replace this interface** — would break all 20+ tests using MagicMock

### style_learner.py fetch_subreddit_corpus
- Phase 1: `client.get(f"/r/{subreddit}/top.json", {t: "all", limit, after})` paginated up to `pages`
- Phase 2: `client.get(f"/r/{subreddit}/hot.json", {limit})` + dedup by permalink
- Prints `"  Fetching page N/M..."` progress
- Returns list of normalized post dicts

### extractor.py
- `read_file(path: str) -> str` — reads single file
- `read_codebase(path: str) -> str` — walks dir, concatenates files
- No URL support

### cli_product.py
- Lines 14-20: `if args.from_file`, `elif args.from_dir`, `elif args.description`
- `raw_text` passed to AI for profile extraction
- `--from-url` would add `elif args.from_url: raw_text = read_url(args.from_url)`

### display.py
- `print_posts(posts, verbose=False)` — header + per-post lines
- `print_subreddits(subs)` — header + per-sub lines
- `print_text(label, content)` — `"=== label ===\n{content}"`
- No console injection — tests use `patch("sys.stdout", StringIO())`

### test_display.py
- `buf = StringIO(); with patch("sys.stdout", buf): print_posts(...)`
- Checks string containment: `"python" in out`, `"1,468,454" in out`
- Rich `Console()` bypasses `sys.stdout` patch — tests will fail if rich is not injectable

### cli_scan.py + cli.py (scan subcommands)
- `cmd_scan_setup_cron(args)` at line 57: prints crontab line
- `cli.py` scan subparsers at lines 240-275
- `scan daemon` can be a new subcommand alongside `setup-cron`

### scanner.py
- Already loads `~/.reddit-toolkit/.env` via `dotenv` at lines 13-16
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` env vars available if user set them
- `run_scan(profile, dry_run, top_n, threshold, reddit_client, notion_push_fn)` — `reddit_client` injected

### pyproject.toml
- Current deps: requests, anthropic, notion-client, python-dotenv
- Need to add: praw, newspaper3k, rich, schedule

---

## Design Decisions

### 1. PRAW — Optional Enhancement Layer

**Do NOT replace `RedditClient`.** Add `reddit_toolkit/praw_client.py` with `PRAWClient`:
- Same `.get(path, params) -> dict` interface via `praw.Reddit.subreddit()` mapping
- New `.fetch_comments_for_post(permalink: str, limit: int = 20) -> list[str]` method
- `style_learner.py`: after fetching posts, if `isinstance(client, PRAWClient)`, call `fetch_comments_for_post` for top-N posts and append comment text to corpus
- Activated in `cli_style.py cmd_style_learn`: check if `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` set → use `PRAWClient`, else `RedditClient()`
- Gracefully degrade: if PRAW fails, log warning and continue with posts-only

**PRAWClient.get() mapping strategy:**
- `/r/{sub}/top.json` with `t=all` → `reddit.subreddit(sub).top(time_filter="all", limit=params["limit"])` → serialize to same dict schema as anonymous API
- `/r/{sub}/hot.json` → `reddit.subreddit(sub).hot(limit=params["limit"])`
- Returns same structure: `{"data": {"after": None, "children": [{"kind": "t3", "data": {...}}]}}`

**Existing tests unchanged** — they mock `RedditClient` via MagicMock; PRAWClient is a different code path.

### 2. newspaper3k — URL Ingestion

- Add `read_url(url: str) -> str` to `extractor.py`
- Uses `newspaper.Article(url)` → `.download()` → `.parse()` → returns `.text`
- Raises `ValueError` if article text is empty
- `cli_product.py`: add `--from-url` to `product create` parser; `elif args.from_url: raw_text = read_url(args.from_url)`
- `test_extractor.py`: add `TestReadUrl` with mock `newspaper.Article`

### 3. rich — Terminal Formatting

- Rewrite `display.py` to use `rich.console.Console`, `rich.table.Table`, `rich.panel.Panel`
- Add optional `console` param to all 3 functions: `print_posts(posts, verbose=False, console=None)`
- Default: `console = Console()` inside function (auto-detects TTY)
- Tests: pass `Console(file=StringIO())` to capture output; update assertions to match new format strings

**New output format:**
- `print_posts`: `Table` with columns: #, Title (truncated 60 chars), Score, Comments, Sub
- `print_subreddits`: `Table` with columns: #, Name, Subscribers, Description (truncated 50 chars)
- `print_text`: `Panel` with label as title

### 4. schedule — Scan Daemon

- Add `cmd_scan_daemon(args)` to `cli_scan.py`
- Parse `--interval` value: regex `^(\d+)(h|m|d)$`; h→hours, m→minutes, d→days
- Use `schedule.every(N).hours/minutes/days.do(job_fn)`
- `job_fn` calls `run_scan(...)` with the loaded profile
- Loop: `while True: schedule.run_pending(); time.sleep(60)`
- Ctrl+C (`KeyboardInterrupt`) → `print("Daemon stopped.")` + exit 0
- Add `scan daemon` subparser to `cli.py`: `--product` (required), `--interval` (default "8h"), `--dry-run` flag

---

## Files Changed

| File | Change |
|------|--------|
| `reddit_toolkit/praw_client.py` | NEW — PRAWClient with .get() + .fetch_comments_for_post() |
| `reddit_toolkit/style_learner.py` | UPDATE — optionally enrich corpus with comments if PRAWClient |
| `reddit_toolkit/cli_style.py` | UPDATE — use PRAWClient when env vars set |
| `reddit_toolkit/extractor.py` | UPDATE — add read_url() |
| `reddit_toolkit/cli_product.py` | UPDATE — add --from-url argument |
| `reddit_toolkit/display.py` | REWRITE — use rich tables/panels with injectable console |
| `reddit_toolkit/cli_scan.py` | UPDATE — add cmd_scan_daemon() |
| `reddit_toolkit/cli.py` | UPDATE — add scan daemon subparser |
| `pyproject.toml` | UPDATE — add praw, newspaper3k, rich, schedule |
| `tests/test_praw_client.py` | NEW — PRAWClient unit tests |
| `tests/test_extractor.py` | UPDATE — add TestReadUrl |
| `tests/test_display.py` | UPDATE — inject Console(file=buf) instead of patching sys.stdout |

---

## Non-Goals

- No removal of existing `RedditClient`
- No auth UI for PRAW credentials
- No schedule persistence across restarts (no job history file)
- No newspaper3k caching
