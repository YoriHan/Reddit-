# Diff Report: Host Spec vs Peer Spec

## Divergence 1: Profile storage structure
**Host**: `~/.reddit-toolkit/products/<slug>/profile.json` + separate `subreddits.json`
**Peer**: `~/.reddit-toolkit/profiles/{id}.json` (flat, subreddits embedded in profile)

**Evidence**: No existing persistence layer in codebase (`cli.py:1-236` has no file I/O). Both approaches are viable.
**Resolution**: **conceded** — peer's flat single-file approach is simpler. Embedding subreddits in `profile.json` eliminates a second file and makes the profile self-contained. `spec.md` updated.

---

## Divergence 2: selftext field in `_normalise_post`
**Host**: Didn't mention this.
**Peer**: `content.py:8` `_normalise_post` does not include `selftext`. AI scoring needs it. Recommends adding to `_normalise_post` rather than a separate API call. Notes that existing test fixtures have `"selftext": ""`.

**Evidence**: Verified at `content.py:8-18` — confirmed `selftext` is absent. Reddit API returns it in the same payload.
**Resolution**: **patched** — spec updated to include `selftext` as a field addition in `_normalise_post`. This is a small but important change for scoring quality.

---

## Divergence 3: CLI file splitting
**Host**: All handlers in `cli.py`
**Peer**: Split into `cli_product.py`, `cli_scan.py`, `cli_notion.py`

**Evidence**: `cli.py:1-236` already has 236 lines. Adding ~8 new command handlers would push it past 500 lines.
**Resolution**: **conceded** — peer's split is better for maintainability. `spec.md` updated.

---

## Divergence 4: python-dotenv dependency
**Host**: Not included.
**Peer**: `python-dotenv>=1.0.0` — loads `~/.reddit-toolkit/.env` in cron context where env vars aren't set.

**Evidence**: `writer.py:12` reads `os.environ.get("ANTHROPIC_API_KEY")`. In cron, this env var will not be set unless sourced. `python-dotenv` solves this cleanly.
**Resolution**: **conceded** — adding `python-dotenv`. `spec.md` updated.

---

## Divergence 5: extractor.py as separate file
**Host**: `_collect_codebase_text()` inside `product.py`
**Peer**: Separate `reddit_toolkit/extractor.py`

**Evidence**: No evidence either way from code. Design preference.
**Resolution**: **conceded** — peer's separate module is more testable (test file: `tests/test_extractor.py`). `spec.md` updated.

---

## Divergence 6: Notion database auto-creation
**Host**: User manually creates database.
**Peer**: `reddit-toolkit notion setup --product ID` auto-creates the database using `client.databases.create()`.

**Evidence**: `notion-client` SDK supports `databases.create()`. Auto-creation reduces friction significantly.
**Resolution**: **conceded** — auto-creation is better UX. `spec.md` updated.

---

## Divergence 7: Interactive confirmation on profile creation
**Host**: Didn't mention this.
**Peer**: After AI extraction, show draft profile and ask `Save? [y/N/edit]`.

**Evidence**: No precedent in existing code, but important UX detail — AI extraction is imperfect.
**Resolution**: **patched** — added interactive confirmation step to spec.

---

## Divergence 8: Local opportunities JSONL + `scan show` command
**Host**: No local storage of opportunities; only Notion.
**Peer**: `~/.reddit-toolkit/state/{id}.opportunities.jsonl` + `scan show` command for local review.

**Evidence**: Useful for debugging/backfill. If Notion is down, scan results aren't lost.
**Resolution**: **patched** — added JSONL storage and `scan show`/`notion push` commands.

---

## Divergence 9: Score threshold — 6 vs 7
**Host**: 6/10
**Peer**: 7/10, configurable per-product in profile JSON.

**Evidence**: No data-driven basis for either. Higher threshold → fewer, higher-quality opportunities.
**Resolution**: **patched** — use 7 as default, configurable per-product via `scan_threshold` field in profile. User can override at runtime with `--threshold`.

---

## Open: Click vs argparse
Both specs note the complexity concern. Peer recommends click; host recommends staying with argparse.
**Disposition**: **escalated** — needs user decision. See Q below.

---

## Open: One Notion DB per product or shared DB
**Disposition**: **escalated** — needs user decision. See Q below.
