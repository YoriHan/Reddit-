# Peer Spec (from independent investigation)

## Key points summary

1. Top-level command: `style` (not `learn`) — `style learn / mimic / list / show`
2. Pagination in new `style_learner.py` (not content.py) — owns pagination state
3. Product info: only `--product <id>` — no inline `--describe`
4. Corpus cap: 200 posts × 100 char body preview (not top-50 by score)
5. TTL: 7 days, `--force` flag
6. Includes `style list` command
7. Includes `--topic` hint for mimic
8. Progress indicator: "Fetching page N/M..."
9. `--no-cache` flag on mimic (re-runs learn with pages=5 inline)
10. slugify() reuse from profile_store for storage key normalization

Full peer spec available in agent output file.
