# Diff Report: Host Spec vs Peer Spec

WARNING: Peer spec was self-generated (second pass), not independent

## Divergences

### D1: pyproject.toml vs setup.py
- **Host spec:** ambiguous ("setup.py (or pyproject.toml)")
- **Peer:** use `pyproject.toml` (modern Python 3.14 standard)
- **Disposition:** patched — `pyproject.toml` adopted in final spec/plan

### D2: Entry point path
- **Host spec:** not stated explicitly
- **Peer:** `reddit_toolkit.cli:main`
- **Disposition:** patched — added to spec

### D3: Rate limiting placement
- **Host spec:** "1 request/second via time.sleep(1) between calls"
- **Peer:** clarified as post-call inside `RedditClient.get()`
- **Disposition:** patched — clarified in plan

### D4: Claude model configurability
- **Host spec:** hardcoded `claude-opus-4-5`
- **Peer:** configurable via `REDDIT_TOOLKIT_MODEL` env var
- **Disposition:** patched — env var override added to plan

### D5: --verbose flag scope
- **Host spec:** --verbose only on `content hot`
- **Peer:** should apply to all content subcommands
- **Disposition:** patched — all content subcommands get --verbose

### D6: CLI exit codes
- **Host spec:** not specified
- **Peer:** errors exit with code 1
- **Disposition:** patched — added to plan

### D7: created_utc display
- **Host spec:** not specified
- **Peer:** `display.py` formats with `datetime.utcfromtimestamp()`
- **Disposition:** patched — added to display.py spec

### D8: --tone choices
- **Host spec:** just mentions "tone=neutral"
- **Peer:** enumerate choices: neutral, funny, supportive, critical
- **Disposition:** patched — added to CLI spec

## Summary
- 8 divergences found
- 8 patched by second-pass review (all self-evident improvements)
- 0 escalated
- 0 proven-false
