# Spec: Reddit Toolkit — Discover Content, Subreddits, Write Posts

**HEAD SHA:** 4c7ea28
**Branch:** ship/reddit-toolkit-discover-content-subreddits-write-posts
**Date:** 2026-04-11

---

## Context

This is a greenfield Python CLI toolkit located at `/Users/yorihan/Reddit小工具`. The directory currently contains only `.ship/` metadata; no application code exists yet. The toolkit has three functional pillars:

1. **Content discovery** — browse trending/top/rising posts by subreddit or globally
2. **Subreddit discovery** — search, explore by topic, list popular subreddits
3. **Writing assistance** — generate post titles, write post bodies, draft comments (powered by Claude API)

---

## Environment Facts (verified by investigation)

| Item | Finding | Source |
|------|---------|--------|
| Python version | 3.14.3 at `/opt/homebrew/bin/python3` | `python3 --version` |
| `requests` | 2.33.1 installed system-wide | `pip3 list` |
| `anthropic` | 0.94.0 installed system-wide | `pip3 list` |
| `pytest` | 9.0.3 installed | `python3 -m pytest --version` |
| Reddit JSON API | Accessible — requires `User-Agent` header with descriptive string; 429 if bare requests | Tested live |
| Reddit auth | Not required for read-only endpoints | Tested live |
| `ANTHROPIC_API_KEY` | Read from env var `ANTHROPIC_API_KEY` (standard SDK behaviour) | `anthropic` SDK docs |
| Trending subreddits API | `/api/trending_subreddits.json` returns 429/error — not usable | Tested live |
| Subreddit popular | `/subreddits/popular.json` works | Tested live |
| Post fields available | `title`, `score`, `url`, `num_comments`, `subreddit`, `author`, `selftext`, `created_utc`, `permalink` | Live API |

---

## Architecture

### Project Layout

```
/Users/yorihan/Reddit小工具/
├── reddit_toolkit/
│   ├── __init__.py
│   ├── cli.py               # Entry point: argparse top-level dispatch
│   ├── reddit_client.py     # Thin wrapper around Reddit JSON API
│   ├── content.py           # Content discovery logic
│   ├── subreddits.py        # Subreddit discovery logic
│   ├── writer.py            # Claude-powered writing assistance
│   └── display.py           # Formatting/display helpers (tabular output)
├── tests/
│   ├── __init__.py
│   ├── test_reddit_client.py
│   ├── test_content.py
│   ├── test_subreddits.py
│   └── test_writer.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Module Responsibilities

**`reddit_client.py`**
- `RedditClient` class
- Single `get(path, params)` method: builds URL, sets `User-Agent`, calls `requests.get`, raises on HTTP error, returns parsed JSON
- `User-Agent` string: `"RedditToolkit/0.1.0 (by /u/toolkit_user)"`
- Rate-limit: 1 request/second via simple `time.sleep(1)` between calls (Reddit guideline)
- Raises `RedditAPIError` (custom exception) on non-2xx

**`content.py`**
- `get_hot_posts(subreddit, limit=10)` → list of post dicts
- `get_top_posts(subreddit, limit=10, timeframe="week")` → list of post dicts; timeframe: `hour|day|week|month|year|all`
- `get_rising_posts(subreddit, limit=10)` → list of post dicts
- `search_posts(query, subreddit=None, limit=10, sort="relevance")` → list of post dicts
  - If `subreddit` given: `/r/{subreddit}/search.json?q=...&restrict_sr=1`
  - Otherwise: `/search.json?q=...`
- All return normalised dicts with keys: `title`, `score`, `url`, `subreddit`, `author`, `num_comments`, `permalink`, `created_utc`

**`subreddits.py`**
- `get_popular_subreddits(limit=20)` → list of subreddit dicts
- `search_subreddits(query, limit=10)` → list of subreddit dicts
  - Uses `/subreddits/search.json?q=...` endpoint
- `get_subreddit_info(name)` → single subreddit dict with `display_name`, `title`, `subscribers`, `public_description`, `url`
- `explore_by_topic(topic, limit=10)` → wrapper around `search_subreddits` with topic as query; returns subreddit dicts
- All return normalised dicts with keys: `display_name`, `title`, `subscribers`, `description`, `url`

**`writer.py`**
- Requires `ANTHROPIC_API_KEY` env var — raises `WriterConfigError` if missing
- `generate_post_title(subreddit, topic, context="")` → list of 3–5 title suggestions
- `write_post_body(subreddit, title, context="")` → string (markdown body)
- `generate_comment(post_title, post_body, post_context="", tone="neutral")` → string
- All functions call `anthropic.Anthropic().messages.create()` with `model` taken from env var `REDDIT_TOOLKIT_MODEL` (default `"claude-opus-4-5"`) and appropriate system + user prompts
- Prompts include subreddit context to tailor tone/style

**`display.py`**
- `print_posts(posts, verbose=False)` — numbered list; verbose adds score/comments/url; always formats `created_utc` (Unix timestamp) as human-readable `datetime.utcfromtimestamp()`
- `print_subreddits(subreddits)` — numbered list with subscriber count and description
- `print_text(label, content)` — for writer output

**`cli.py`**
- Top-level `main()` using `argparse` with subcommands:
  ```
  reddit-toolkit content hot     [--subreddit SUBREDDIT] [--limit N] [--verbose]
  reddit-toolkit content top     [--subreddit SUBREDDIT] [--limit N] [--time TIMEFRAME] [--verbose]
  reddit-toolkit content rising  [--subreddit SUBREDDIT] [--limit N] [--verbose]
  reddit-toolkit content search  QUERY [--subreddit SUBREDDIT] [--limit N] [--sort SORT] [--verbose]
  reddit-toolkit subs popular    [--limit N]
  reddit-toolkit subs search     QUERY [--limit N]
  reddit-toolkit subs info       SUBREDDIT
  reddit-toolkit subs explore    TOPIC [--limit N]
  reddit-toolkit write title     --subreddit SUBREDDIT --topic TOPIC [--context TEXT]
  reddit-toolkit write body      --subreddit SUBREDDIT --title TITLE [--context TEXT]
  reddit-toolkit write comment   --post-title TITLE [--post-body BODY] [--tone {neutral,funny,supportive,critical}]
  ```
- Default `--subreddit` for content commands: `"all"` (Reddit's aggregate front)
- Installed as `reddit-toolkit` console script via `pyproject.toml` entry point `reddit_toolkit.cli:main`
- CLI errors print a message to stderr and exit with code 1

---

## Reddit API Endpoints Used

| Feature | Endpoint | Verified |
|---------|----------|---------|
| Hot posts | `GET /r/{sub}/hot.json` | Yes |
| Top posts | `GET /r/{sub}/top.json?t={time}` | Yes |
| Rising posts | `GET /r/{sub}/rising.json` | Yes |
| Search posts | `GET /search.json?q=...` or `/r/{sub}/search.json?q=...&restrict_sr=1` | Yes |
| Popular subreddits | `GET /subreddits/popular.json` | Yes |
| Search subreddits | `GET /subreddits/search.json?q=...` | Yes |
| Subreddit info | `GET /r/{sub}/about.json` | Yes |
| Trending subreddits | `/api/trending_subreddits.json` | Blocked (429) — NOT used |

All API calls use base URL `https://www.reddit.com` + path.

---

## Error Handling

- `RedditAPIError` — raised by `RedditClient.get()` for HTTP errors; caught in CLI with user-friendly message
- `WriterConfigError` — raised by `writer.py` if `ANTHROPIC_API_KEY` missing; caught in CLI with instruction to set env var
- `requests.exceptions.ConnectionError` — caught in CLI, shown as network error
- Invalid subreddit (404) — `RedditAPIError` with status code in message

---

## Testing Strategy

- **Unit tests with mocking** — `RedditClient.get` is mocked; content/subreddit/writer functions tested with fixture data
- `tests/test_reddit_client.py` — tests `get()` method: success path, HTTP error, rate limiting behaviour
- `tests/test_content.py` — tests each content function against mocked `RedditClient`
- `tests/test_subreddits.py` — tests each subreddit function against mocked `RedditClient`
- `tests/test_writer.py` — tests each writer function against mocked `anthropic.Anthropic().messages.create`
- All tests use `unittest.mock.patch` and `pytest`
- No real network calls in tests

---

## Constraints & Non-Goals

- No OAuth/authentication flow (read-only API is sufficient for discovery)
- No persistent storage or caching
- No web UI or API server
- No async/concurrent requests
- No interactive TUI (pure CLI subcommands)
- `requests` and `anthropic` are the only third-party dependencies (both already installed)

---

## Investigation Summary

- 0 existing source files found in project root (greenfield)
- 8 live Reddit API endpoints tested
- 1 endpoint found broken (`/api/trending_subreddits.json` → 429)
- `requests` 2.33.1 and `anthropic` 0.94.0 pre-installed system-wide
- `pytest` 9.0.3 available
