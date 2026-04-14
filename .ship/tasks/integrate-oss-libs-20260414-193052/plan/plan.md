# Plan: Integrate PRAW, newspaper4k, rich, schedule

task_id: integrate-oss-libs-20260414-193052

## Dependency Wave

```
Wave 1 (parallel): Story 1 (newspaper4k), Story 2 (rich), Story 3 (schedule)
Wave 2 (sequential): Story 4 (PRAW)
```

Story 4 imports from `praw_client.py` (new file); must wait until Wave 1 is merged so no merge conflicts.

---

## Story 1: newspaper4k — URL Ingestion for Product Create

**Files:** `reddit_toolkit/extractor.py`, `reddit_toolkit/cli_product.py`, `reddit_toolkit/cli.py`, `tests/test_extractor.py`, `pyproject.toml`

### Steps

- [ ] Open `pyproject.toml`. In `dependencies` list, add as the last entry:
```
    "newspaper4k>=0.9.3",
```

- [ ] Open `reddit_toolkit/extractor.py`. After line 1 (`import os`), add:
```python
import newspaper
```
Then add after `read_codebase` function (end of file):
```python

def read_url(url: str) -> str:
    """Download and parse article text from a URL using newspaper4k."""
    article = newspaper.Article(url)
    article.download()
    article.parse()
    if not article.text.strip():
        raise ValueError(f"No article text found at {url}")
    return article.text
```

- [ ] Open `reddit_toolkit/cli_product.py`. At line 6, the current line is:
```python
from .extractor import read_file, read_codebase
```
  Replace it with:
```python
from .extractor import read_file, read_codebase, read_url
```
  Then in `cmd_product_create`, lines 12-20 currently read:
```python
    raw_text = ""
    if args.from_dir:
        print(f"Reading codebase from {args.from_dir}...")
        raw_text = read_codebase(args.from_dir)
    elif args.from_file:
        print(f"Reading file {args.from_file}...")
        raw_text = read_file(args.from_file)
    elif args.description:
        raw_text = args.description
```
  Replace those lines with:
```python
    raw_text = ""
    if args.from_dir:
        print(f"Reading codebase from {args.from_dir}...")
        raw_text = read_codebase(args.from_dir)
    elif args.from_file:
        print(f"Reading file {args.from_file}...")
        raw_text = read_file(args.from_file)
    elif args.from_url:
        print(f"Fetching article from {args.from_url}...")
        try:
            raw_text = read_url(args.from_url)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.description:
        raw_text = args.description
```

- [ ] Open `reddit_toolkit/cli.py`. At line 238, the current line is:
```python
    pc_p.add_argument("--from-dir", default=None, metavar="DIR")
```
  After line 238 (before `pc_p.set_defaults(func=cmd_product_create)` at line 239), insert:
```python
    pc_p.add_argument("--from-url", default=None, metavar="URL", help="Fetch product info from a URL")
```

- [ ] Open `tests/test_extractor.py`. Add at top-level imports (after existing imports):
```python
from unittest.mock import patch, MagicMock
```
Then add at end of file:
```python

class TestReadUrl:
    def test_returns_article_text(self):
        mock_article = MagicMock()
        mock_article.text = "This is a great product for developers."
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article):
            from reddit_toolkit.extractor import read_url
            result = read_url("https://example.com")
        assert result == "This is a great product for developers."
        mock_article.download.assert_called_once()
        mock_article.parse.assert_called_once()

    def test_raises_value_error_on_empty_text(self):
        mock_article = MagicMock()
        mock_article.text = "   "
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article):
            from reddit_toolkit.extractor import read_url
            import pytest
            with pytest.raises(ValueError, match="No article text"):
                read_url("https://example.com/empty")

    def test_url_passed_to_article(self):
        mock_article = MagicMock()
        mock_article.text = "some text"
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article) as mock_cls:
            from reddit_toolkit.extractor import read_url
            read_url("https://myproduct.com")
        mock_cls.assert_called_once_with("https://myproduct.com")
```

- [ ] Run tests: `python3 -m pytest tests/test_extractor.py -v`
- [ ] Verify 3 new tests pass, all existing tests still pass
- [ ] Commit: `feat(extractor): add read_url via newspaper4k; product create --from-url`

---

## Story 2: rich — Formatted Terminal Output

**Files:** `reddit_toolkit/display.py`, `tests/test_display.py`, `pyproject.toml`

### Steps

- [ ] Open `pyproject.toml`. In `dependencies` list, add:
```
    "rich>=13.0.0",
```

- [ ] Replace `reddit_toolkit/display.py` entirely with:
```python
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def print_posts(posts, verbose=False, console=None):
    if console is None:
        console = Console()
    if not posts:
        console.print("[dim]No posts found.[/dim]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Title", max_width=60)
    if verbose:
        table.add_column("Score", justify="right")
        table.add_column("Comments", justify="right")
        table.add_column("Date")
        table.add_column("URL")
    table.add_column("Subreddit")
    for i, post in enumerate(posts, 1):
        date_str = ""
        if verbose and post.get("created_utc"):
            date_str = datetime.utcfromtimestamp(post["created_utc"]).strftime("%Y-%m-%d")
        if verbose:
            table.add_row(
                str(i),
                post.get("title", ""),
                str(post.get("score", "")),
                str(post.get("num_comments", "")),
                date_str,
                post.get("url", ""),
                post.get("subreddit", ""),
            )
        else:
            table.add_row(str(i), post.get("title", ""), post.get("subreddit", ""))
    console.print(table)


def print_subreddits(subs, console=None):
    if console is None:
        console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Subreddit")
    table.add_column("Subscribers", justify="right")
    table.add_column("Description", max_width=50)
    for i, sub in enumerate(subs, 1):
        subs_str = f"{sub.get('subscribers', 0):,}" if sub.get("subscribers") else ""
        table.add_row(
            str(i),
            sub.get("display_name", ""),
            subs_str,
            sub.get("description", ""),
        )
    console.print(table)


def print_text(label, content, console=None):
    if console is None:
        console = Console()
    console.print(Panel(content, title=label))
```

- [ ] Replace `tests/test_display.py` with the following (preserves all existing test intent, updates capture mechanism):
```python
import io
from datetime import datetime
from rich.console import Console
from reddit_toolkit.display import print_posts, print_subreddits, print_text


SAMPLE_POST = {
    "title": "Test Post Title",
    "score": 500,
    "url": "https://example.com",
    "subreddit": "python",
    "author": "testuser",
    "num_comments": 42,
    "permalink": "/r/python/comments/abc/test/",
    "created_utc": 1700000000.0,
}

SAMPLE_SUB = {
    "display_name": "python",
    "title": "Python",
    "subscribers": 1468454,
    "description": "The largest Python community.",
    "url": "/r/python/",
}


def capture(func, *args, **kwargs):
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    func(*args, **kwargs, console=console)
    return buf.getvalue()


class TestPrintPosts:
    def test_shows_title(self):
        out = capture(print_posts, [SAMPLE_POST])
        assert "Test Post Title" in out

    def test_shows_index(self):
        out = capture(print_posts, [SAMPLE_POST])
        assert "1" in out

    def test_verbose_shows_score(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "500" in out

    def test_verbose_shows_comments(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "42" in out

    def test_verbose_shows_human_date(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "2023" in out

    def test_non_verbose_no_score(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=False)
        assert "500" not in out

    def test_empty_list_no_crash(self):
        out = capture(print_posts, [])
        assert len(out) >= 0  # no crash


class TestPrintSubreddits:
    def test_shows_display_name(self):
        out = capture(print_subreddits, [SAMPLE_SUB])
        assert "python" in out

    def test_shows_subscribers(self):
        out = capture(print_subreddits, [SAMPLE_SUB])
        assert "1468454" in out or "1,468,454" in out


class TestPrintText:
    def test_shows_label_and_content(self):
        out = capture(print_text, "Title Suggestions", "First title")
        assert "Title Suggestions" in out
        assert "First title" in out
```

- [ ] Run tests: `python3 -m pytest tests/test_display.py -v`
- [ ] Verify all 11 display tests pass
- [ ] Run full suite: `python3 -m pytest -v`
- [ ] Verify no regressions (all previously passing tests still pass)
- [ ] Commit: `feat(display): rewrite with rich tables and injectable console`

---

## Story 3: schedule — Scan Daemon Command

**Files:** `reddit_toolkit/cli_scan.py`, `reddit_toolkit/cli.py`, `pyproject.toml`

### Steps

- [ ] Open `pyproject.toml`. In `dependencies` list, add:
```
    "schedule>=1.2.0",
```

- [ ] Open `reddit_toolkit/cli_scan.py`. Add to top-level imports (after `from .scanner import run_scan`):
```python
import re
import time
import schedule as _schedule
```

- [ ] Add the following function at the end of `cli_scan.py`:
```python

def cmd_scan_daemon(args):
    m = re.fullmatch(r"(\d+)(h|m|d)", args.interval)
    if not m:
        print(f"Error: invalid interval '{args.interval}'. Use e.g. 8h, 30m, 1d.", file=sys.stderr)
        sys.exit(1)
    n, unit = int(m.group(1)), m.group(2)

    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    def job():
        print(f"\nRunning scan for '{args.product}'...")
        run_scan(profile=profile, dry_run=False, top_n=10, threshold=7.0)
        print("Scan complete.")

    if unit == "h":
        _schedule.every(n).hours.do(job)
    elif unit == "m":
        _schedule.every(n).minutes.do(job)
    else:
        _schedule.every(n).days.do(job)

    print(f"Daemon started. Scanning every {args.interval}. Ctrl+C to stop.")
    try:
        while True:
            _schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        sys.exit(0)
```

- [ ] Open `reddit_toolkit/cli.py`. Add import of `cmd_scan_daemon` (update the scan import at line ~261 where `cmd_scan_run`, `cmd_scan_show`, `cmd_scan_setup_cron` are imported):
```python
# Before:
from .cli_scan import cmd_scan_run, cmd_scan_show, cmd_scan_setup_cron
# After:
from .cli_scan import cmd_scan_run, cmd_scan_show, cmd_scan_setup_cron, cmd_scan_daemon
```

- [ ] In `build_parser()` in `cli.py`, after the `setup-cron` subparser block (after `sc_p.set_defaults(func=cmd_scan_setup_cron)`), add:
```python
    # scan daemon
    sdaemon_p = scan_sub.add_parser("daemon", help="Run scan as an in-process daemon on a schedule")
    sdaemon_p.add_argument("--product", required=True, help="Product profile ID")
    sdaemon_p.add_argument("--interval", "-i", default="8h",
                            help="Scan interval (e.g. 8h, 30m, 1d). Default: 8h")
    sdaemon_p.set_defaults(func=cmd_scan_daemon)
```

- [ ] Run smoke test: `python3 -m reddit_toolkit.cli scan --help` (should list `daemon` in subcommands)
- [ ] Run smoke test: `python3 -m reddit_toolkit.cli scan daemon --help` (should show `--product`, `--interval`)
- [ ] Run tests: `python3 -m pytest -v`
- [ ] Verify all tests pass
- [ ] Commit: `feat(scan): add scan daemon command with schedule interval`

---

## Story 4: PRAW — Optional Comment Corpus Enrichment

**Depends on:** Wave 1 complete (no file conflicts)

**Files:** `reddit_toolkit/praw_client.py` (new), `reddit_toolkit/style_learner.py`, `reddit_toolkit/cli_style.py`, `tests/test_praw_client.py` (new), `pyproject.toml`

### Steps

- [ ] Open `pyproject.toml`. In `dependencies` list, add:
```
    "praw>=7.7.0",
```

- [ ] Create `reddit_toolkit/praw_client.py`:
```python
"""Optional PRAW-based Reddit client for comment enrichment.

Activated when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars are set.
Provides the same .get() interface as RedditClient plus .fetch_comments_for_post().
"""
import os
import praw


def _make_reddit():
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "reddit-toolkit/1.0"),
    )


def _serialise_submission(sub):
    return {
        "title": sub.title,
        "score": sub.score,
        "url": sub.url,
        "subreddit": str(sub.subreddit),
        "author": str(sub.author) if sub.author else "[deleted]",
        "num_comments": sub.num_comments,
        "permalink": sub.permalink,
        "created_utc": float(sub.created_utc),
        "selftext": sub.selftext,
    }


class PRAWClient:
    """PRAW-backed client with same .get() interface as RedditClient."""

    def __init__(self):
        self._reddit = _make_reddit()

    def get(self, path: str, params: dict = None) -> dict:
        params = params or {}
        parts = path.strip("/").split("/")
        # Expected paths: r/{sub}/top.json or r/{sub}/hot.json
        if len(parts) < 3 or parts[0] != "r":
            return {"data": {"after": None, "children": []}}
        subreddit_name = parts[1]
        sort = parts[2].replace(".json", "")
        limit = int(params.get("limit", 25))
        sub = self._reddit.subreddit(subreddit_name)
        if sort == "top":
            time_filter = params.get("t", "all")
            listings = list(sub.top(time_filter=time_filter, limit=limit))
        else:
            listings = list(sub.hot(limit=limit))
        children = [{"kind": "t3", "data": _serialise_submission(s)} for s in listings]
        return {"data": {"after": None, "children": children}}

    def fetch_comments_for_post(self, permalink: str, limit: int = 20) -> list:
        """Return top-level comment bodies for a post."""
        submission = self._reddit.submission(url=f"https://www.reddit.com{permalink}")
        submission.comments.replace_more(limit=0)
        comments = []
        for comment in submission.comments[:limit]:
            if hasattr(comment, "body") and comment.body not in ("[deleted]", "[removed]"):
                comments.append(comment.body)
        return comments


def make_praw_client_if_configured():
    """Return PRAWClient if env vars set, else None."""
    if os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"):
        return PRAWClient()
    return None
```

- [ ] Open `reddit_toolkit/style_learner.py`. The function `fetch_subreddit_corpus` at line 5 uses variables `c` (the client, line 19), `all_posts` (list, line 20), and `seen_permalinks` (set, line 21). The function ends with `return all_posts` at line 49.

  Replace the entire `style_learner.py` file with this updated version (adds `import warnings` at top and comment enrichment before `return`):
```python
import warnings

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
    If client is a PRAWClient, also fetches top comments for the first 5 posts.

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

    # Phase 3: optional comment enrichment (PRAWClient only)
    from .praw_client import PRAWClient  # noqa: PLC0415 — lazy to avoid circular at module top
    if isinstance(c, PRAWClient):
        for post in all_posts[:5]:
            try:
                comments = c.fetch_comments_for_post(post["permalink"], limit=10)
                for body in comments:
                    if body.strip():
                        key = f"__comment__{body[:50]}"
                        if key not in seen_permalinks:
                            seen_permalinks.add(key)
                            all_posts.append({**post, "title": body, "selftext": body,
                                              "permalink": key})
            except Exception as e:
                warnings.warn(f"Comment fetch failed for {post.get('permalink')}: {e}")

    return all_posts
```

- [ ] Open `reddit_toolkit/cli_style.py`. At the top of the file, after all existing imports (before the first function definition), add:
```python
from .praw_client import make_praw_client_if_configured
```

- [ ] In `cli_style.py`, at line 32, the current code is:
```python
        posts = fetch_subreddit_corpus(subreddit, pages=pages)
```
  Replace that line with:
```python
        reddit_client = make_praw_client_if_configured()
        posts = fetch_subreddit_corpus(subreddit, pages=pages, client=reddit_client)
```

- [ ] Create `tests/test_praw_client.py`:
```python
import os
from unittest.mock import MagicMock, patch, PropertyMock
import pytest


def make_mock_submission(title="Post", score=100, author="user"):
    sub = MagicMock()
    sub.title = title
    sub.score = score
    sub.url = "https://x.com"
    sub.subreddit = MagicMock()
    sub.subreddit.__str__ = lambda self: "python"
    sub.author = MagicMock()
    sub.author.__str__ = lambda self: author
    sub.num_comments = 5
    sub.permalink = "/r/python/comments/abc/test/"
    sub.created_utc = 1700000000.0
    sub.selftext = ""
    return sub


class TestPRAWClient:
    def test_get_returns_expected_schema(self):
        mock_submission = make_mock_submission()
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.top.return_value = [mock_submission]
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import PRAWClient
                client = PRAWClient()
                result = client.get("/r/python/top.json", {"t": "all", "limit": 10})
        assert "data" in result
        assert "children" in result["data"]
        assert result["data"]["children"][0]["kind"] == "t3"
        data = result["data"]["children"][0]["data"]
        assert data["title"] == "Post"
        assert data["author"] == "user"

    def test_deleted_author_serialised_as_string(self):
        mock_submission = make_mock_submission()
        mock_submission.author = None
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.top.return_value = [mock_submission]
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import PRAWClient
                client = PRAWClient()
                result = client.get("/r/python/top.json", {"t": "all", "limit": 5})
        assert result["data"]["children"][0]["data"]["author"] == "[deleted]"

    def test_make_praw_client_if_configured_returns_none_when_no_env(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")}
        with patch.dict(os.environ, env, clear=True):
            from reddit_toolkit.praw_client import make_praw_client_if_configured
            result = make_praw_client_if_configured()
        assert result is None

    def test_make_praw_client_if_configured_returns_client_when_env_set(self):
        mock_reddit = MagicMock()
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import make_praw_client_if_configured, PRAWClient
                result = make_praw_client_if_configured()
        assert isinstance(result, PRAWClient)
```

- [ ] Run tests: `python3 -m pytest tests/test_praw_client.py -v`
- [ ] Verify 4 new tests pass
- [ ] Run full suite: `python3 -m pytest -v`
- [ ] Verify all tests pass (existing 96 + 4 new = 100+)
- [ ] Commit: `feat(praw): add PRAWClient for optional comment corpus enrichment`

---

## Test Command

```bash
python3 -m pytest -v
```

## Acceptance Verification

After all stories complete:
```bash
python3 -m pytest -v
# → all tests pass (100+ tests)

python3 -m reddit_toolkit.cli product create --help
# → shows --from-url option

python3 -m reddit_toolkit.cli scan daemon --help
# → shows --product, --interval options

python3 -m reddit_toolkit.cli scan --help
# → lists daemon in subcommands
```
