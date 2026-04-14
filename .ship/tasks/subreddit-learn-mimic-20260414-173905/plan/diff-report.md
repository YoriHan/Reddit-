# Diff Report: Host vs Peer Spec

## D1: Top-level command name (`learn` vs `style`)

**Host:** `reddit-toolkit learn run --subreddit python`
**Peer:** `reddit-toolkit style learn --subreddit python`

**Resolution: concede to peer**
`style` is semantically clearer and keeps all style-related commands (`learn`, `mimic`, `list`, `show`) cohesive under one top-level namespace. Code evidence: `cli.py:231` shows `product` and `scan` as top-level namespaces grouping related commands — `style` follows this exact pattern.

**Action:** Updated spec to use `style` top-level.

---

## D2: Pagination location (`content.py` vs `style_learner.py`)

**Host:** add `fetch_subreddit_posts()` to `content.py`
**Peer:** new `style_learner.py` with `fetch_subreddit_corpus()`

**Resolution: concede to peer**
Code evidence: `content.py:30-53` — all 4 functions are single-call, stateless. The pagination loop requires maintaining cursor state, printing progress, and mixing hot+top requests. This belongs in a dedicated module, keeping content.py's single-responsibility intact.

**Action:** Updated spec to use `style_learner.py`.

---

## D3: `--describe` inline product description

**Host:** supports both `--product <id>` AND `--describe "..."` for ad-hoc use
**Peer:** only `--product <id>`

**Resolution: proven — host spec correct**
Code evidence: `cli_product.py:19` — `elif args.description: raw_text = args.description` shows inline text is already a supported pattern in the codebase. The user's original question explicitly asked "how to understand product info, do you have good ideas" — suggesting they want a low-friction path. `--describe` reduces barrier for first-time users significantly.

**Action:** Keep `--describe` in spec alongside `--product`. Mutual exclusion enforced by argparse.

---

## D4: Claude corpus size (top-50 vs 200-post cap)

**Host:** top 50 posts by score
**Peer:** hard cap at 200 posts, ~100 chars body preview each

**Resolution: concede to peer**
200 × 100 chars = ~5,000 tokens — well within Claude limits. More posts = more title pattern diversity. 50 posts risks missing niche patterns. Peer's approach gives Claude a richer signal set while staying within budget.

**Action:** Updated spec to 200-post cap, 100-char body truncation.

---

## D5: Additional items from peer spec (no divergence, just additions)

**patched:** Added `style list` command to host spec.
**patched:** Added `--topic` flag to `style mimic`.
**patched:** Added progress indicator "Fetching page N/M..." to `style learn`.
**patched:** Added `--no-cache` flag to `style mimic` (runs inline learn with pages=5).

---

## Final dispositions

| ID | Item | Disposition |
|----|------|-------------|
| D1 | `learn` vs `style` command | conceded — peer correct |
| D2 | pagination in content.py vs style_learner.py | conceded — peer correct |
| D3 | `--describe` flag | proven — host correct |
| D4 | corpus size 50 vs 200 | conceded — peer correct |
| D5 | list/topic/progress/no-cache | patched — added from peer |

No escalated items.
