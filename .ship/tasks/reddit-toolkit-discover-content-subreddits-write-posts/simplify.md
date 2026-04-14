# Simplify Phase

## Summary

51/51 tests pass. Code changed across 4 files.

## Changes

### `reddit_toolkit/cli.py`
- Extracted the repeated `except RedditAPIError / except requests.exceptions.ConnectionError` block
  that appeared identically in 8 command handlers into a single `@contextlib.contextmanager`
  called `_reddit_errors()`. Each handler now uses `with _reddit_errors():` instead of
  duplicating two except clauses.
- Moved `import requests` to the top-level import block (was mixed in with local imports).

### `reddit_toolkit/content.py`
- Extracted the `if client is None: client = RedditClient()` guard (repeated in every public
  function) into a one-liner helper `_client(client)`. All four fetch functions now call
  `_client(client).get(...)` directly, eliminating 4 copies of the same two-line pattern.

### `reddit_toolkit/subreddits.py`
- Same `_client(client)` helper added; removed the three identical `if client is None`
  guards from `get_popular_subreddits`, `search_subreddits`, and `get_subreddit_info`.

### `reddit_toolkit/writer.py`
- Inlined the single-use `_get_model()` helper directly into `_call_claude`. The function
  existed only to wrap one `os.environ.get` call and added indirection without benefit.

## Files Changed
- `/Users/yorihan/Reddit小工具/reddit_toolkit/cli.py`
- `/Users/yorihan/Reddit小工具/reddit_toolkit/content.py`
- `/Users/yorihan/Reddit小工具/reddit_toolkit/subreddits.py`
- `/Users/yorihan/Reddit小工具/reddit_toolkit/writer.py`
