# Concerns

## Story 1: style_store.py

**Bug (non-blocking): `save()` mutates caller's dict**
- File: reddit_toolkit/style_store.py:25-26
- `save()` sets `data["subreddit"]` and `data["learned_at"]` in-place. Caller's dict is silently modified. Fix: use `data = {**data, "subreddit": ..., "learned_at": ...}` internally.

**Bug (non-blocking): `is_stale()` crashes on naive datetime strings**
- File: reddit_toolkit/style_store.py:48
- If `learned_at` has no UTC offset (e.g. manually edited file), `datetime.fromisoformat()` returns naive datetime and the subtraction with `datetime.now(timezone.utc)` raises TypeError. Fix: `if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)`.

## Story 2: style_learner.py

**Cosmetic: progress message has leading spaces**
- File: reddit_toolkit/style_learner.py (print statement)
- Prints `"  Fetching page N/M..."` (2 leading spaces) vs spec `"Fetching page N/M..."`. No functional impact.
