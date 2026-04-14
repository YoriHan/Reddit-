# QA Report: Reddit Toolkit CLI

**Date:** 2026-04-11
**Verdict:** PASS
**Task:** reddit-toolkit-discover-content-subreddits-write-posts

---

## Test Execution

### Unit Test Suite

```
pytest tests/ -v
51 passed in 3.27s
```

All 51 tests pass across:
- `tests/test_cli.py` — 12 tests
- `tests/test_content.py` — 9 tests
- `tests/test_display.py` — 10 tests
- `tests/test_reddit_client.py` — 5 tests
- `tests/test_subreddits.py` — 8 tests
- `tests/test_writer.py` — 7 tests

---

## Spec Criteria Verification

### Architecture / Project Layout

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `reddit_toolkit/__init__.py` exists | PASS | File present |
| `reddit_toolkit/cli.py` — argparse entry point | PASS | File present, imports verified |
| `reddit_toolkit/reddit_client.py` | PASS | File present |
| `reddit_toolkit/content.py` | PASS | File present |
| `reddit_toolkit/subreddits.py` | PASS | File present |
| `reddit_toolkit/writer.py` | PASS | File present |
| `reddit_toolkit/display.py` | PASS | File present |
| `tests/` with all test files | PASS | 6 test files present |
| `requirements.txt` | PASS | `requests>=2.33.1`, `anthropic>=0.94.0` |
| `pyproject.toml` with console script entry point | PASS | `reddit-toolkit = "reddit_toolkit.cli:main"` |

### reddit_client.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `RedditClient` class with `get(path, params)` | PASS | Implemented |
| `User-Agent: RedditToolkit/0.1.0 (by /u/toolkit_user)` | PASS | `RedditClient.USER_AGENT` verified |
| Base URL `https://www.reddit.com` | PASS | `test_correct_base_url` passed |
| `time.sleep(1)` rate limiting | PASS | `test_rate_limit_sleep_called` passed |
| `RedditAPIError` raised on HTTP error | PASS | `test_http_error_raises_reddit_api_error` passed |
| No sleep on `ConnectionError` | PASS | `test_sleep_not_called_on_connection_error` passed |

### content.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `get_hot_posts(subreddit, limit)` | PASS | `test_calls_correct_endpoint` |
| `get_top_posts(subreddit, limit, timeframe)` | PASS | `test_calls_correct_endpoint_with_timeframe` |
| `get_rising_posts(subreddit, limit)` | PASS | `test_calls_correct_endpoint` |
| `search_posts(query, subreddit, limit, sort)` | PASS | `test_global_search`, `test_subreddit_restricted_search` |
| Normalised post dict keys: title, score, url, subreddit, author, num_comments, permalink, created_utc | PASS | `test_post_has_required_keys` + direct verify |
| Default subreddit = "all" | PASS | `test_default_subreddit_is_all` |
| search with subreddit uses `/r/{sub}/search.json?restrict_sr=1` | PASS | `test_subreddit_restricted_search` |

### subreddits.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `get_popular_subreddits(limit)` → `/subreddits/popular.json` | PASS | `test_calls_correct_endpoint` |
| `search_subreddits(query, limit)` → `/subreddits/search.json?q=...` | PASS | `test_calls_search_endpoint` |
| `get_subreddit_info(name)` → `/r/{name}/about.json` | PASS | `test_calls_about_endpoint` |
| `explore_by_topic(topic, limit)` delegates to `search_subreddits` | PASS | `test_is_alias_for_search` |
| Normalised subreddit keys: display_name, title, subscribers, description, url | PASS | `test_result_has_required_keys` + direct verify |
| Missing `data` key raises `KeyError` | PASS | `test_missing_data_key_raises_key_error` |

### writer.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Raises `WriterConfigError` if no `ANTHROPIC_API_KEY` | PASS | `test_raises_if_no_api_key`, live CLI test |
| `generate_post_title` returns list of strings | PASS | `test_returns_list_of_strings` |
| Numbered list parsed correctly into titles | PASS | Manual parse test: 4 titles returned correctly |
| `write_post_body` returns markdown string | PASS | `test_returns_string` |
| `generate_comment` returns string | PASS | `test_returns_string` |
| Tone included in prompt | PASS | `test_tone_included_in_prompt` |
| Subreddit in prompt | PASS | `test_subreddit_in_prompt` |
| Model from `REDDIT_TOOLKIT_MODEL` env var (default `claude-opus-4-5`) | PASS | `test_calls_messages_create_with_model` |

### display.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `print_posts(posts, verbose)` shows numbered list | PASS | `test_shows_title`, `test_shows_index` |
| Verbose shows score, comments, URL, author | PASS | `test_verbose_shows_score`, `test_verbose_shows_comments` |
| `created_utc` formatted as human-readable date | PASS | `test_verbose_shows_human_date`; `_format_timestamp(1700000000.0)` → `2023-11-14 22:13 UTC` |
| Non-verbose omits score | PASS | `test_non_verbose_no_score` |
| Empty list handled gracefully | PASS | `test_empty_list_no_crash` |
| `print_subreddits(subs)` shows display_name and subscriber count | PASS | `test_shows_display_name`, `test_shows_subscribers` |
| `print_text(label, content)` shows both | PASS | `test_shows_label_and_content` |

### cli.py

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `reddit-toolkit` console script installed | PASS | `which reddit-toolkit` → `/opt/homebrew/bin/reddit-toolkit` |
| `content hot/top/rising/search` subcommands | PASS | `--help` output verified |
| `subs popular/search/info/explore` subcommands | PASS | `--help` output verified |
| `write title/body/comment` subcommands | PASS | `--help` output verified |
| Default `--subreddit` = `"all"` for content commands | PASS | `test_content_hot_default_subreddit_is_all` |
| `RedditAPIError` → exit code 1 | PASS | `test_reddit_api_error_exits_1` |
| `WriterConfigError` → exit code 1 + message | PASS | Live test: `Error: ANTHROPIC_API_KEY ... exit 1` |
| `ConnectionError` handled gracefully | PASS | Tested via mock in test_cli.py |

---

## Issues Found Beyond Spec

### Minor Discrepancy: `get_subreddit_info` return key name

The spec states two things:
1. `get_subreddit_info(name)` returns a dict with keys `display_name`, `title`, `subscribers`, **`public_description`**, `url`
2. "All return normalised dicts with keys: `display_name`, `title`, `subscribers`, **`description`**, `url`"

The implementation uses `description` (from statement 2), not `public_description`. The "All return normalised dicts" statement is the canonical one, and the implementation is internally consistent (display.py and cli.py both read `description`). This is a documentation inconsistency in the spec, not a code bug. No functional impact.

### Sleep timing on HTTP errors

`time.sleep(1)` is called before `raise_for_status()`, meaning a 1-second delay also occurs on HTTP 4xx/5xx error responses (not just successful ones). This is a minor behaviour note — the spec says "1 request/second via simple `time.sleep(1)` between calls" without specifying whether it should apply to error responses. All tests pass given this implementation.

---

## No Services Started / No Cleanup Needed

This is a CLI-only tool (no server, no database, no containers). No services were started during QA.
