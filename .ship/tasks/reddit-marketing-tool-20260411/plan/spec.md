# Spec: Reddit Marketing Intelligence Tool
HEAD SHA: (local, no remote)
Date: 2026-04-11

---

## 1. Problem Statement

The existing `reddit-toolkit` is a general-purpose CLI for reading Reddit and generating AI-written content. It has no concept of a "product" and no pipeline for finding marketing opportunities automatically.

Users want: feed in a product description once → tool automatically scans Reddit daily for trending discussions → AI identifies where the product is naturally relevant → draft posts are pushed to Notion for human review → user manually posts approved content.

The tool must support **multiple different products** (different users / products reuse the same tool).

---

## 2. Confirmed Scope (user decisions)

| Decision | Outcome |
|---|---|
| Auto-posting | No — tool generates content only, user posts manually |
| Context input | Multi-product; user provides product description OR codebase directory |
| Trigger | Cron job (external to Python) |
| Review UX | Notion database — user reviews pages |

---

## 3. Existing Code Inventory

All claims verified by reading source files.

| File | Key functions | Notes |
|---|---|---|
| `reddit_client.py:10` | `RedditClient.get(path, params)` | Unauthenticated GET only; 1s sleep per call (`time.sleep(1)` at line 30); raises `RedditAPIError` on HTTP error |
| `content.py:29` | `get_hot_posts(subreddit, limit, client)` | Returns list of normalised post dicts |
| `content.py:34` | `get_top_posts(subreddit, limit, timeframe, client)` | timeframe: hour/day/week/month/year/all |
| `content.py:39` | `get_rising_posts(subreddit, limit, client)` | |
| `content.py:44` | `search_posts(query, subreddit, limit, sort, client)` | |
| `subreddits.py:26` | `get_popular_subreddits(limit, client)` | |
| `subreddits.py:31` | `search_subreddits(query, limit, client)` | |
| `subreddits.py:36` | `get_subreddit_info(name, client)` | |
| `subreddits.py:44` | `explore_by_topic(topic, limit, client)` | Thin wrapper over `search_subreddits` |
| `writer.py:10` | `_make_client()` | Reads `ANTHROPIC_API_KEY` env var; raises `WriterConfigError` if missing |
| `writer.py:20` | `_call_claude(client, system, user)` | Uses `REDDIT_TOOLKIT_MODEL` env var, default `claude-opus-4-5` |
| `writer.py:30` | `generate_post_title(subreddit, topic, context)` | Returns list[str] |
| `writer.py:62` | `write_post_body(subreddit, title, context)` | Returns str (markdown) |
| `writer.py:81` | `generate_comment(post_title, post_body, post_context, tone)` | Returns str |
| `cli.py:124` | `build_parser()` | 3 top-level commands: content, subs, write |
| `cli.py:226` | `main()` | Entry point registered in `pyproject.toml:16` |
| `display.py:13` | `print_posts(posts, verbose)` | Numbered list output |
| `display.py:28` | `print_subreddits(subs)` | |
| `display.py:43` | `print_text(label, content)` | |
| `pyproject.toml:10` | deps | `requests>=2.33.1`, `anthropic>=0.94.0` |

Tests use `unittest.mock` throughout (`patch("requests.get", ...)`, `patch("reddit_toolkit.writer._make_client", ...)`). No real API calls in tests.

---

## 4. Reuse vs New

### Reused as-is
- `RedditClient.get()` — used by scanner to fetch posts
- `get_hot_posts()`, `get_rising_posts()` — called by scanner
- `search_subreddits()` — called during subreddit recommendation
- `_make_client()`, `_call_claude()` — reused by new writer functions
- `display.py` — unchanged

### Modified
- `writer.py` — add 2 new functions: `score_opportunities()`, `generate_opportunity_draft()`
- `cli.py` — add 2 new top-level commands: `product`, `scan` (+ `schedule` helper)
- `pyproject.toml` + `requirements.txt` — add `notion-client>=2.2.1`

### New files
- `reddit_toolkit/product.py` — product profile CRUD
- `reddit_toolkit/scanner.py` — scan pipeline
- `reddit_toolkit/notion.py` — Notion push

---

## 5. Product Profile Design

### Storage location
Global, not per-project. Stored at:
```
~/.reddit-toolkit/
  products/
    <slug>/
      profile.json      # product metadata
      subreddits.json   # AI-recommended subreddits (cached)
```

`slug` = lowercased, hyphenated version of product name (e.g. "My App" → "my-app").

### profile.json schema
```json
{
  "name": "My App",
  "slug": "my-app",
  "description": "One paragraph describing what the product does",
  "target_audience": "Who uses this product",
  "key_features": ["feature 1", "feature 2"],
  "value_proposition": "Core benefit in one sentence",
  "keywords": ["keyword1", "keyword2"],
  "created_at": "2026-04-11T09:00:00Z",
  "updated_at": "2026-04-11T09:00:00Z"
}
```

### Context input options (mutually exclusive)
1. `--description "..."` — user types a free-text description; Claude extracts the structured fields
2. `--from-file path/to/README.md` — reads one file; Claude extracts structured fields
3. `--from-dir path/to/codebase` — walks directory, collects `.md` files + `README*` + top-level `.py`/`.ts`/`.js` files; concatenates up to 40,000 chars; Claude extracts structured fields

All three paths pass the raw text to a single `_extract_profile_from_text(raw: str, name: str) -> dict` function in `product.py` that calls Claude.

### subreddits.json schema
```json
{
  "generated_at": "2026-04-11T09:00:00Z",
  "subreddits": [
    {
      "name": "python",
      "display_name": "r/python",
      "subscribers": 1200000,
      "reason": "Why this subreddit is relevant to the product"
    }
  ]
}
```

Subreddit recommendations are generated once on `product subreddits` command and cached. Refreshed only when `--refresh` flag is passed.

---

## 6. Scanner Pipeline Design

Command: `reddit-toolkit scan --product NAME [--dry-run] [--top N]`

### Steps
1. Load `profile.json` and `subreddits.json` for the product
2. For each subreddit (up to 10 subreddits per scan to limit API calls):
   - Fetch `get_hot_posts(subreddit, limit=25)`
   - Fetch `get_rising_posts(subreddit, limit=10)`
   - Deduplicate by `permalink`
3. Collect all posts across subreddits. Deduplicate again by `permalink`.
4. Score in batches of 10: call `score_opportunities(posts_batch, profile)` → returns list of `{post, score: 0-10, hook_angle: str}`.
5. Filter: keep posts with `score >= 6`.
6. Sort by score descending. Take top `N` (default: 5).
7. For each selected opportunity: call `generate_opportunity_draft(opportunity, profile)` → returns `{title: str, body: str}`.
8. If `--dry-run`: print to stdout, do not push to Notion.
9. Otherwise: push each result to Notion via `push_opportunity()`.
10. Print summary: "Scanned X posts across Y subreddits. Found Z opportunities. Pushed to Notion."

### Scoring prompt design (in writer.py)
`score_opportunities(posts: list[dict], profile: dict) -> list[dict]`

System prompt tells Claude it is a marketing analyst who knows the product. For each post it returns:
```json
[{"permalink": "/r/.../...", "score": 7, "hook_angle": "This discussion is about X which directly relates to Y feature of our product"}]
```
Claude returns JSON array. Posts not in output are scored 0.

### Draft generation (in writer.py)
`generate_opportunity_draft(opportunity: dict, profile: dict) -> dict`

Returns `{"title": str, "body": str}`. The post body is natural, not spammy — it contributes value to the discussion first, then organically mentions the product. Max 300 words.

---

## 7. Notion Integration Design

### SDK choice
`notion-client>=2.2.1` (official Notion Python SDK). Simpler than raw `requests` for Notion's block API.

### Required env vars
- `NOTION_TOKEN` — Notion integration token
- `NOTION_DATABASE_ID` — the database to push pages to

### Database properties (user must create these columns in Notion)
| Property | Type | Notes |
|---|---|---|
| Title | title | Draft post title |
| Status | select | Review / Approved / Published / Rejected (default: Review) |
| Product | rich_text | product slug |
| Target Subreddit | rich_text | r/subredditname |
| Opportunity Score | number | 0–10 |
| Hook Angle | rich_text | Why this is relevant |
| Source Post Title | rich_text | Original Reddit post title |
| Source Post URL | url | Link to source post |
| Scan Date | date | When scan ran |

### Page body
Post body (markdown) is stored as the page content (Notion paragraph blocks), not in a property (properties have a 2000-char limit; post bodies can be longer).

### notion.py responsibilities
- `NotionConfigError` — raised when env vars missing
- `push_opportunity(opportunity_data: dict) -> str` — creates page, returns page URL
- `_make_notion_client()` — reads env vars

---

## 8. Cron Integration Design

The `scan` command is designed to be cron-safe:
- Exits with code 0 on success
- Writes logs to `~/.reddit-toolkit/logs/scan-<date>.log`
- Does not require a TTY

### Helper command
`reddit-toolkit schedule --product NAME --time HH:MM`

This does NOT write to crontab. It prints a ready-to-paste crontab line:
```
0 9 * * * /path/to/reddit-toolkit scan --product my-app >> ~/.reddit-toolkit/logs/scan.log 2>&1
```
User adds it manually with `crontab -e`.

Reason: modifying crontab programmatically is fragile and platform-dependent.

---

## 9. New CLI Commands

```
reddit-toolkit product init --name NAME [--description TEXT | --from-file FILE | --from-dir DIR]
reddit-toolkit product list
reddit-toolkit product show NAME
reddit-toolkit product subreddits NAME [--refresh] [--limit N]
reddit-toolkit scan --product NAME [--dry-run] [--top N]
reddit-toolkit schedule --product NAME --time HH:MM
```

All new commands follow the existing pattern: handler function → registered with `set_defaults(func=...)`.

---

## 10. New Files and Responsibilities

| File | Responsibility | Key functions |
|---|---|---|
| `reddit_toolkit/product.py` | Product profile CRUD | `create_profile()`, `load_profile()`, `list_profiles()`, `recommend_subreddits()`, `_extract_profile_from_text()`, `_collect_codebase_text()` |
| `reddit_toolkit/scanner.py` | Scan pipeline orchestration | `run_scan(product_slug, dry_run, top_n)` — calls content.py, writer.py, notion.py |
| `reddit_toolkit/notion.py` | Notion API push | `push_opportunity(data)`, `NotionConfigError`, `_make_notion_client()` |

### Modified files
- `reddit_toolkit/writer.py` — add `score_opportunities()`, `generate_opportunity_draft()`
- `reddit_toolkit/cli.py` — add `cmd_product_*`, `cmd_scan`, `cmd_schedule` handlers + parser sections

---

## 11. New Dependencies

| Package | Version | Why |
|---|---|---|
| `notion-client` | `>=2.2.1` | Official Notion Python SDK; handles auth headers, pagination, block types |

---

## 12. Open Questions (for user)

1. **Scan log history**: Should the tool track which posts have already been scored to avoid re-pushing the same post to Notion on repeated scans? (Propose: yes, store seen `permalink` set in `~/.reddit-toolkit/products/<slug>/seen_posts.json`)
2. **Opportunity score threshold**: Is 6/10 the right cutoff? Or should user configure it per product?
3. **Subreddit count**: Scan up to 10 subreddits per run — is that enough, or too many (takes ~3-5 minutes at 1s rate limit)?
4. **No-opportunity run**: When scan finds 0 opportunities above threshold, should it still push a "No results" summary page to Notion, or just log to console?

---

## 13. Testing Strategy

Following existing pattern (unittest.mock, no real API calls):
- `test_product.py` — mock filesystem and Claude calls; test profile CRUD, codebase text collection truncation, slug generation
- `test_scanner.py` — mock `get_hot_posts`, `get_rising_posts`, `score_opportunities`, `generate_opportunity_draft`, `push_opportunity`; test dedup, filtering, top-N selection
- `test_notion.py` — mock `notion_client.Client`; test property mapping, missing env var raises `NotionConfigError`
- Add to `test_writer.py` — test `score_opportunities` returns correct shape; test `generate_opportunity_draft` returns title + body
