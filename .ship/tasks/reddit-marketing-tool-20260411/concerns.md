## Task 3 — profile_store.py (PASS_WITH_CONCERNS)

1. `profile_store.py:25` — `slugify("")` or `slugify("!!!")` returns `""`, causing `save` to write `.json` (hidden file). No guard present.
2. `tests/test_profile_store.py:11-13` — empty/all-special-chars slugify edge case untested.
3. `profile_store.py:37` — `save` mutates the caller's dict in place (sets `updated_at`). Undocumented side-effect.

## Task 2 — extractor.py (PASS_WITH_CONCERNS)

1. `extractor.py:53` — separator chars `"\n\n---\n\n"` (7 chars each) not counted against `max_chars`, causing minor over-budget output.
2. `tests/test_extractor.py:35` — max_chars assertion bound too loose (500-char margin for 2000-char limit).
3. No test for depth-limiting behavior (depth > 3 files not excluded in tests).
4. Only `.git` tested for hidden dir skipping; `__pycache__`/`node_modules`/`.venv` untested.

## Task 6 — notion_pusher.py (PASS_WITH_CONCERNS)

1. `notion_pusher.py:125-127` — AI Analysis paragraph in `_build_blocks` concatenates hook_angle + reasoning without 2000-char truncation. Can hit Notion API limit.
2. No test for `_split_text("")` edge case (implementation correct but unverified by test).

## Task 5 — scanner.py (PASS_WITH_CONCERNS)

1. `tests/test_scanner.py:98-110` — No test covers `notion_push_fn(None)` empty-scan signal path.
2. `tests/test_scanner.py:95` — `assert len(result.opportunities) <= 2` too weak; should be `== 2`.
3. `tests/test_scanner.py:63` — `patch("time.sleep")` global patch; fragile if import style changes.
4. `scanner.py:135` — `_append_opportunities` called before dry_run guard; dry_run still creates state file.

## Task 7 — CLI wiring (PASS_WITH_CONCERNS, 1 bug fixed)

1. ~~`cli_product.py:70` — `profile["subreddits"].append(...)` KeyError on old profiles~~ **FIXED** with `setdefault`.
2. `cli_scan.py:45` — `--last 0` returns all lines (minor UX edge case).
