# Peer Spec: Reddit Toolkit (Second Pass)

WARNING: Second spec was self-generated, not independent

## Second-Pass Review Findings

### Placeholder scan
- No placeholders found in main spec. All module functions named concretely.

### Contradiction scan
- No contradictions. Trending subreddits endpoint correctly excluded since it returns 429.

### Coverage scan
Missing items found:

1. **`requirements.txt` format** — spec says both `requests` and `anthropic` are only third-party deps. Correct. But `pyproject.toml` vs `setup.py` is left ambiguous. Decision needed: use `pyproject.toml` (modern standard for Python 3.14).

2. **`reddit-toolkit` as installed command** — spec says installed via console_scripts. Need to specify entry point path: `reddit_toolkit.cli:main`.

3. **Rate limiting scope** — spec says `time.sleep(1)` per request. This should be in `RedditClient.get()` directly after each call, not managed by callers.

4. **Claude model name** — spec says `claude-opus-4-5`. Should verify this model ID is current for `anthropic` 0.94.0. Safer to use `claude-opus-4-5` or make it configurable via env var `REDDIT_TOOLKIT_MODEL` (defaulting to `claude-opus-4-5`).

5. **`write comment` CLI args** — `--post-body` is optional; `--tone` options should be enumerated: `neutral`, `funny`, `supportive`, `critical`.

6. **Default subreddit for `content` commands** — spec says default is `"all"`. The Reddit API endpoint for global feed is `/r/all/hot.json` which does work (maps to `r/all` subreddit). Correct.

7. **`explore_by_topic` distinction** — spec notes it's a wrapper around `search_subreddits`. This is correct, but the CLI should still present it as a distinct command for discoverability. No change needed.

### Ambiguity scan
- **Post normalisation** — `created_utc` is a Unix timestamp. Should display layer convert to human-readable? Spec doesn't specify. Recommendation: `display.py` formats it with `datetime.utcfromtimestamp()`.
- **`--verbose` flag** — only specified for `content hot`. Should apply to all content commands.
- **Error exit codes** — on CLI error, should exit with code 1. Not specified in spec. Add this.

## Additions to Incorporate into Main Spec
1. Use `pyproject.toml` (not `setup.py`)
2. Entry point: `reddit_toolkit.cli:main`
3. `time.sleep(1)` is post-call inside `RedditClient.get()`
4. Model configurable via `REDDIT_TOOLKIT_MODEL` env var, default `claude-opus-4-5`
5. `--verbose` on all content subcommands
6. CLI errors exit with code 1
7. `display.py` formats `created_utc` as human-readable
8. `--tone` choices: `neutral`, `funny`, `supportive`, `critical`
