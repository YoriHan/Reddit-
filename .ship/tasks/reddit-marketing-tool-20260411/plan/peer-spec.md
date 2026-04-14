# Peer Spec: Reddit Marketing Tool

---

## Existing Code Inventory

### `reddit_toolkit/__init__.py` (line 1)
Empty file (1 line). Acts only as a package marker. No exports.

---

### `reddit_toolkit/reddit_client.py` (lines 1–35)
**Class `RedditAPIError`** (line 5): Custom exception for HTTP-level failures.

**Class `RedditClient`** (line 10):
- `BASE_URL = "https://www.reddit.com"` (line 11)
- `USER_AGENT = "RedditToolkit/0.1.0 (by /u/toolkit_user)"` (line 12)
- `get(path, params) -> dict` (line 14): Makes a unauthenticated GET to the Reddit JSON API. Sleeps 1 second after every request (line 30) to respect rate limits. Raises `RedditAPIError` on HTTP errors.

Uses only the public `*.json` endpoints — no OAuth, no Reddit API credentials required.

---

### `reddit_toolkit/content.py` (lines 1–52)
**`_client(client)`** (line 4): Returns the passed client or a fresh `RedditClient()`.

**`_normalise_post(data)`** (line 8): Maps raw Reddit API post fields to a canonical dict with keys: `title`, `score`, `url`, `subreddit`, `author`, `num_comments`, `permalink`, `created_utc`.

**`_extract_posts(response)`** (line 21): Filters `kind == "t3"` children from a listing response and normalises each.

**`get_hot_posts(subreddit, limit, client)`** (line 29): Calls `/r/{subreddit}/hot.json`.

**`get_top_posts(subreddit, limit, timeframe, client)`** (line 34): Calls `/r/{subreddit}/top.json` with timeframe param (`t`).

**`get_rising_posts(subreddit, limit, client)`** (line 39): Calls `/r/{subreddit}/rising.json`.

**`search_posts(query, subreddit, limit, sort, client)`** (line 44): Calls either `/r/{subreddit}/search.json` (with `restrict_sr=1`) or global `/search.json`.

---

### `reddit_toolkit/subreddits.py` (lines 1–45)
**`_normalise_subreddit(data)`** (line 8): Maps to `display_name`, `title`, `subscribers`, `description` (from `public_description`), `url`.

**`_extract_subreddits(response)`** (line 18): Filters `kind == "t5"` children.

**`get_popular_subreddits(limit, client)`** (line 26): Calls `/subreddits/popular.json`.

**`search_subreddits(query, limit, client)`** (line 31): Calls `/subreddits/search.json`.

**`get_subreddit_info(name, client)`** (line 36): Calls `/r/{name}/about.json`; raises `KeyError` if `data` key missing.

**`explore_by_topic(topic, limit, client)`** (line 44): Alias for `search_subreddits`.

---

### `reddit_toolkit/writer.py` (lines 1–112)
**`WriterConfigError`** (line 5): Raised when `ANTHROPIC_API_KEY` is absent.

**`_make_client()`** (line 10): Reads `ANTHROPIC_API_KEY` from env; raises `WriterConfigError` if missing.

**`_call_claude(client, system_prompt, user_prompt)`** (line 20): Calls `client.messages.create()` using `model = os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5")`, `max_tokens=1024`. Returns `response.content[0].text`.

**`generate_post_title(subreddit, topic, context)`** (line 30): Returns a list of 3–5 title strings stripped of leading numbering.

**`write_post_body(subreddit, title, context)`** (line 62): Returns a markdown string.

**`generate_comment(post_title, post_body, post_context, tone)`** (line 81): Returns a comment string; tone selects from `neutral`, `funny`, `supportive`, `critical`.

---

### `reddit_toolkit/display.py` (lines 1–47)
**`_format_timestamp(utc_ts)`** (line 4): Converts Unix timestamp to `"YYYY-MM-DD HH:MM UTC"`.

**`print_posts(posts, verbose)`** (line 13): Numbered list; verbose adds score, comments, date, URL, author.

**`print_subreddits(subreddits)`** (line 28): Numbered list with subscriber count and truncated description.

**`print_text(label, content)`** (line 43): Prints a labelled block wrapped in `===` banners.

---

### `reddit_toolkit/cli.py` (lines 1–236)
Entry point. Uses `argparse` with two levels of subcommands.

**Top-level commands and their handlers:**
- `content hot` → `cmd_content_hot` (line 30)
- `content top` → `cmd_content_top` (line 36)
- `content rising` → `cmd_content_rising` (line 42)
- `content search` → `cmd_content_search` (line 48)
- `subs popular` → `cmd_subs_popular` (line 59)
- `subs search` → `cmd_subs_search` (line 65)
- `subs info` → `cmd_subs_info` (line 71)
- `subs explore` → `cmd_subs_explore` (line 81)
- `write title` → `cmd_write_title` (line 87)
- `write body` → `cmd_write_body` (line 99)
- `write comment` → `cmd_write_comment` (line 111)

**`_handle_error(msg, exit_code)`** (line 14): Prints to stderr, calls `sys.exit`.

**`_reddit_errors()`** (line 19): Context manager catching `RedditAPIError` and `ConnectionError`.

**`build_parser()`** (line 124) / **`main()`** (line 226): Standard argparse bootstrap.

---

### `pyproject.toml`
- Package: `reddit-toolkit`, version `0.1.0`
- Entry point: `reddit-toolkit = "reddit_toolkit.cli:main"` (line 16)
- Current dependencies: `requests>=2.33.1`, `anthropic>=0.94.0`
- Python: `>=3.10`

### `requirements.txt`
Mirrors pyproject.toml: `requests>=2.33.1`, `anthropic>=0.94.0`

---

### Test files (summary of behavioral contracts)
- `tests/test_reddit_client.py`: Verifies correct URL construction, `User-Agent` header, `time.sleep(1)` per request, `RedditAPIError` on HTTP 4xx/5xx.
- `tests/test_content.py`: Verifies endpoint paths, parameter shapes, normalised post keys, kind-filtering.
- `tests/test_subreddits.py`: Verifies endpoint paths, normalised subreddit keys, `KeyError` on missing `data`.
- `tests/test_writer.py`: Verifies `WriterConfigError` on missing env var, model name from env, list return type for titles, string return for body/comment.
- `tests/test_display.py`: Verifies output contains titles/subscriber counts/labels; verbose vs non-verbose branching.
- `tests/test_cli.py`: Integration-style tests patching module-level functions; verifies argument wiring, error exit codes.

---

## Reuse vs New

### Keep as-is (no changes)
| File | Reason |
|---|---|
| `reddit_toolkit/reddit_client.py` | `RedditClient.get()` is all that is needed for all new Reddit reads. The 1-second sleep already handles basic rate limiting. |
| `reddit_toolkit/content.py` | `get_hot_posts`, `get_top_posts`, `get_rising_posts`, `search_posts` are the exact primitives the scanner pipeline will use. |
| `reddit_toolkit/subreddits.py` | `search_subreddits` and `get_subreddit_info` will be used for the AI subreddit recommendation step. |
| `reddit_toolkit/display.py` | `print_posts`, `print_subreddits`, `print_text` are reused for CLI output in new commands. |

### Modify (extend, not rewrite)
| File | What changes |
|---|---|
| `reddit_toolkit/writer.py` | Add two new functions: `score_post_for_product(post, profile)` and `generate_opportunity_draft(post, profile, hook_angle)`. These follow the same `_call_claude` pattern already established at line 20. The `max_tokens=1024` cap will need to increase to ~2048 for draft generation. |
| `reddit_toolkit/cli.py` | Add three new top-level command groups: `product`, `scan`, and `notion`. Reuse `_handle_error` and `_reddit_errors`. `build_parser()` gets extended with new subparsers; `main()` is untouched. |
| `pyproject.toml` / `requirements.txt` | Add new dependencies (see New Dependencies section). |

### New (net-new files)
Everything in the product profile system, scanner pipeline, Notion integration, cron support, and profile extraction is new. See New Files section for the full list.

---

## Product Profile Design

### Schema

A product profile is stored as a single JSON file. The canonical schema:

```json
{
  "id": "my-saas-product",
  "name": "My SaaS Product",
  "created_at": "2026-04-11T00:00:00Z",
  "updated_at": "2026-04-11T00:00:00Z",
  "description": "One-paragraph human-readable description of what the product does.",
  "problem_solved": "The pain point the product eliminates.",
  "target_audience": ["indie hackers", "startup founders", "developers"],
  "key_features": ["feature A", "feature B"],
  "tone": "casual",
  "avoid_topics": ["competitor names", "pricing"],
  "subreddits": [
    {
      "name": "SideProject",
      "why": "audience of indie hackers who launch tools",
      "added_by": "ai"
    },
    {
      "name": "webdev",
      "why": "manually added by user",
      "added_by": "user"
    }
  ],
  "keywords": ["keyword1", "keyword2"],
  "codebase_summary": "Optional: AI-extracted summary injected during profile creation."
}
```

**Field notes:**
- `id`: slug derived from `name` (lowercase, hyphenated). Used as the filename and as a CLI argument.
- `subreddits[].added_by`: either `"ai"` (from recommendation) or `"user"` (manually added via CLI).
- `tone`: hints for draft generation. Values: `casual`, `professional`, `technical`.
- `codebase_summary`: populated when user runs `product create --from-codebase`. Optional, can be empty.

### Storage location

Profiles live in a dedicated directory that the tool creates on first use:

```
~/.reddit-toolkit/profiles/{product-id}.json
```

The directory `~/.reddit-toolkit/` is also used to store scan run state (see Scanner Pipeline).

A helper module `reddit_toolkit/profile_store.py` manages read/write/list of profiles from this path. The path can be overridden via env var `REDDIT_TOOLKIT_DATA_DIR` for testability.

### Codebase content → profile extraction

When the user runs `product create --from-codebase ./path/to/dir` (or `--from-file ./README.md`):

1. The tool reads specified files (text files only; recursively up to a depth limit of 3, or a single file if `--from-file` is used). File content is concatenated up to a token budget (~8000 chars).
2. The concatenated content is passed to Claude via a new `extract_profile_from_codebase(text)` function in `writer.py`. The system prompt instructs Claude to return a JSON object matching the profile schema fields (`description`, `problem_solved`, `target_audience`, `key_features`, `keywords`).
3. The returned JSON is merged into a new profile object. The user confirms or edits interactively before saving.

The interactive confirmation step is important: the AI extraction is a starting point, not authoritative. The CLI should print the draft profile and ask `Save? [y/N/edit]`. If `edit`, open in `$EDITOR`.

---

## Scanner Pipeline Design

### Step-by-step flow

```
[Trigger: cron or CLI]
        │
        ▼
1. Load product profile  ─── profile_store.load(product_id)
        │
        ▼
2. Resolve subreddit list ── profile["subreddits"] → list of names
        │
        ▼
3. For each subreddit:
   a. Fetch hot posts      ── content.get_hot_posts(sub, limit=25)
   b. Fetch rising posts   ── content.get_rising_posts(sub, limit=10)
   c. Deduplicate by permalink
        │
        ▼
4. Filter out already-seen posts
   ── Load seen-permalinks set from ~/.reddit-toolkit/state/{product-id}.seen.json
   ── Discard any post whose permalink is in the set
        │
        ▼
5. Score each remaining post via AI
   ── writer.score_post_for_product(post, profile) → {"score": 0-10, "hook_angle": "...", "reasoning": "..."}
   ── Batch calls: one Claude call per post (or batched if Anthropic batch API available)
        │
        ▼
6. Threshold filter
   ── Keep posts with score >= OPPORTUNITY_THRESHOLD (default: 7; configurable per product)
        │
        ▼
7. Generate draft for each opportunity
   ── writer.generate_opportunity_draft(post, profile, hook_angle) → {"title": "...", "body": "..."}
        │
        ▼
8. Persist opportunities
   ── Append to ~/.reddit-toolkit/state/{product-id}.opportunities.jsonl (newline-delimited JSON)
   ── Update seen-permalinks set
        │
        ▼
9. Push to Notion
   ── notion_client.push_opportunity(product_id, post, score_result, draft)
        │
        ▼
10. Print summary to stdout / log file
```

### Scoring prompt design

`score_post_for_product(post, profile)` calls Claude with:
- **System**: "You are a Reddit marketing analyst. Given a product description and a Reddit post, score how relevant this post is as an opportunity to naturally mention or promote the product. Return JSON only."
- **User**: includes `profile["description"]`, `profile["problem_solved"]`, `profile["target_audience"]`, `profile["keywords"]`, and the post's `title`, `score`, `subreddit`, and first 500 chars of `selftext` (if available in future).
- **Expected response schema**: `{"score": <int 0-10>, "hook_angle": "<one sentence>", "reasoning": "<one sentence>"}`
- Claude is instructed to return raw JSON with no surrounding text. Response is parsed with `json.loads()`; if parsing fails, the post is skipped and the error is logged.

### Scoring threshold

- Default: `score >= 7`
- Configurable: stored as `"scan_threshold": 7` in the product profile JSON.
- Override at runtime: `scan run --product my-product --threshold 6`

### Rate limiting

The existing `time.sleep(1)` in `RedditClient.get()` covers Reddit API calls. For Claude scoring calls, a small sleep (0.5s) is inserted between calls in `scanner.py` to avoid hammering the Anthropic API during bulk scans. The scanner processes subreddits sequentially (not concurrently) to keep complexity low.

### Deduplication

The seen-set file `~/.reddit-toolkit/state/{product-id}.seen.json` stores a JSON array of permalink strings. It is loaded at the start of each scan and written back at the end. On first run, the file does not exist and is treated as an empty set.

---

## Notion Integration Design

### Database schema

One Notion database per product. The database is created by the tool on first push (using `notion_client.ensure_database(product_id, profile)`). The database title is `{product["name"]} — Reddit Opportunities`.

**Properties:**

| Property name | Notion type | Notes |
|---|---|---|
| `Post Title` | Title (required) | Title of the Reddit post |
| `Subreddit` | Select | e.g. `SideProject` |
| `Score` | Number | AI relevance score 0–10 |
| `Hook Angle` | Rich text | One-sentence angle from AI |
| `Reddit URL` | URL | `https://reddit.com{permalink}` |
| `Reddit Score` | Number | Reddit upvote score |
| `Comments` | Number | Reddit comment count |
| `Scanned At` | Date | UTC timestamp of scan run |
| `Status` | Select | Default `Draft`; options: `Draft`, `Posted`, `Skipped` |
| `Draft Title` | Rich text | AI-generated post title suggestion |
| `Draft Body` | Rich text | AI-generated post body (truncated to Notion's 2000-char limit per block; full text in page body) |
| `Product` | Select | product id, for multi-product databases if user prefers one DB |
| `Reasoning` | Rich text | AI one-sentence justification |

### Page body structure

Each Notion page (one per opportunity) has the following block structure:

```
H1: [Post Title]

H2: Original Post
  Paragraph: r/{subreddit} — Score: {reddit_score} | Comments: {comments}
  Paragraph: {permalink URL}

H2: AI Analysis
  Paragraph: Score: {ai_score}/10
  Paragraph: Hook: {hook_angle}
  Paragraph: Reasoning: {reasoning}

H2: Draft Post
  H3: Title
  Paragraph: {draft_title}
  H3: Body
  Paragraph: {draft_body}  (full text, split into ≤2000-char blocks)
```

### SDK choice

Use the official `notion-client` Python SDK (`notion-client>=2.2.0`). This provides:
- `Client(auth=NOTION_TOKEN)`
- `client.databases.create()`
- `client.pages.create()`
- `client.databases.query()` (for deduplication check on re-runs)

The Notion integration token is read from `NOTION_TOKEN` env var. The parent page ID where new databases are created is read from `NOTION_PARENT_PAGE_ID` env var.

### Deduplication on push

Before creating a new page, `notion_client.push_opportunity()` queries the database for existing pages with a matching `Reddit URL` property. If found, it skips (or optionally updates) rather than creating a duplicate.

### New module: `reddit_toolkit/notion_pusher.py`

Encapsulates all Notion SDK calls:
- `ensure_database(product_id, profile, notion_client) -> database_id`
- `push_opportunity(database_id, post, score_result, draft, notion_client) -> page_id`
- `_build_properties(post, score_result, draft) -> dict`
- `_build_blocks(post, score_result, draft) -> list`

The database ID is persisted to `~/.reddit-toolkit/notion/{product-id}.notion.json` after first creation so subsequent scans reuse it.

---

## Cron Integration Design

### Approach: system cron + CLI wrapper

The tool does not manage cron itself. It exposes a command `scan run --product {id}` that is a self-contained, non-interactive process suitable for cron invocation. The user installs the cron entry manually.

Rationale: macOS and Linux both have `crontab`. Adding cron management to the tool would create platform-specific complexity with minimal payoff. The CLI prints an exact crontab line for the user to copy.

### Setup command

`reddit-toolkit scan setup-cron --product {id} [--hour 8] [--minute 0]`

This command:
1. Detects the full path to the `reddit-toolkit` binary using `shutil.which("reddit-toolkit")`.
2. Prints a ready-to-paste crontab line:
   ```
   0 8 * * * /full/path/to/reddit-toolkit scan run --product my-product >> ~/.reddit-toolkit/logs/my-product.log 2>&1
   ```
3. Instructs the user to run `crontab -e` and paste it.
4. Does not modify crontab automatically (avoids surprising mutations).

### Log output

`scan run` writes structured log lines to stdout (captured by cron redirect). Each line is prefixed with a UTC timestamp. Example:
```
2026-04-11T08:00:01Z [INFO] Starting scan for product: my-product
2026-04-11T08:00:03Z [INFO] Fetching r/SideProject hot (25 posts)
2026-04-11T08:00:05Z [INFO] Scoring 18 new posts...
2026-04-11T08:00:22Z [INFO] 3 opportunities found above threshold 7
2026-04-11T08:00:25Z [INFO] Pushed 3 pages to Notion
2026-04-11T08:00:25Z [INFO] Scan complete.
```

Log files accumulate in `~/.reddit-toolkit/logs/`. No automatic rotation is built in (user can use `logrotate` if needed).

### Environment variables for cron

Because cron runs with a minimal environment, users must set `ANTHROPIC_API_KEY`, `NOTION_TOKEN`, and `NOTION_PARENT_PAGE_ID` in a `.env` file. The `scan run` command uses `python-dotenv` to load `~/.reddit-toolkit/.env` automatically before doing anything else.

---

## New CLI Commands

All new commands are added as additional top-level command groups in `cli.py`'s `build_parser()`.

### `product` group

#### `reddit-toolkit product create`
```
reddit-toolkit product create
  --name NAME           Human-readable product name (required)
  --id ID               Slug id (optional; auto-derived from name if omitted)
  --from-codebase DIR   Extract profile from files in DIR (optional)
  --from-file FILE      Extract profile from a single file (optional)
```
Creates and saves a new product profile. If `--from-codebase` or `--from-file` is given, runs AI extraction and presents a confirmation prompt before saving.

#### `reddit-toolkit product list`
```
reddit-toolkit product list
```
Lists all saved product profiles with their id, name, number of tracked subreddits.

#### `reddit-toolkit product show`
```
reddit-toolkit product show PRODUCT_ID
```
Prints the full JSON of the profile, formatted.

#### `reddit-toolkit product edit`
```
reddit-toolkit product edit PRODUCT_ID
```
Opens the profile JSON in `$EDITOR` (falls back to `nano`). Validates JSON on save.

#### `reddit-toolkit product add-subreddit`
```
reddit-toolkit product add-subreddit PRODUCT_ID SUBREDDIT_NAME
  [--why "reason string"]
```
Appends a subreddit to the profile's `subreddits` list with `added_by: "user"`.

#### `reddit-toolkit product recommend-subreddits`
```
reddit-toolkit product recommend-subreddits PRODUCT_ID
  [--limit 10]
```
Calls Claude (via a new `recommend_subreddits(profile)` function in `writer.py`) to suggest subreddits. Prints suggestions. Asks `Add all? [y/N]` or lets user pick by number.

---

### `scan` group

#### `reddit-toolkit scan run`
```
reddit-toolkit scan run
  --product PRODUCT_ID  (required)
  --threshold INT       Override score threshold (optional)
  --dry-run             Score posts but do not push to Notion (optional)
  --no-draft            Skip draft generation (optional)
```
Executes the full scanner pipeline. Safe to call from cron.

#### `reddit-toolkit scan show`
```
reddit-toolkit scan show
  --product PRODUCT_ID  (required)
  [--last N]            Show last N scan results (default: 20)
```
Reads `~/.reddit-toolkit/state/{product-id}.opportunities.jsonl` and prints a formatted table of opportunities from the most recent scan run(s).

#### `reddit-toolkit scan setup-cron`
```
reddit-toolkit scan setup-cron
  --product PRODUCT_ID  (required)
  --hour INT            Hour in 24h format (default: 8)
  --minute INT          Minute (default: 0)
```
Prints a crontab line for the user to paste. Does not modify crontab.

---

### `notion` group

#### `reddit-toolkit notion setup`
```
reddit-toolkit notion setup
  --product PRODUCT_ID  (required)
```
Creates the Notion database for the product (if it does not already exist), saves the database ID locally, and prints a confirmation with the Notion URL.

#### `reddit-toolkit notion push`
```
reddit-toolkit notion push
  --product PRODUCT_ID  (required)
  [--since DATE]        Push opportunities from a specific date onward (ISO date, optional)
```
Manually pushes opportunities from the local JSONL file to Notion. Useful for backfilling or re-pushing after a Notion outage.

---

## New Files

### `reddit_toolkit/profile_store.py`
**Purpose:** CRUD for product profile JSON files on disk.

Key functions:
- `profiles_dir() -> Path`: returns `Path(os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit/profiles")).expanduser()`
- `load(product_id: str) -> dict`: reads and parses the profile JSON; raises `ProfileNotFoundError` if absent.
- `save(profile: dict) -> None`: writes `~/.reddit-toolkit/profiles/{id}.json`; creates directory if needed.
- `list_profiles() -> list[dict]`: returns all profiles as a list.
- `delete(product_id: str) -> None`
- `ProfileNotFoundError(Exception)`: raised when a profile id does not exist.

---

### `reddit_toolkit/scanner.py`
**Purpose:** Implements the full scanner pipeline (Steps 1–10 from the Scanner Pipeline section).

Key functions:
- `run_scan(product_id: str, threshold: int = None, dry_run: bool = False, no_draft: bool = False) -> ScanResult`
- `_fetch_posts(subreddits: list[str], client=None) -> list[dict]`: calls `get_hot_posts` and `get_rising_posts` per subreddit, deduplicates.
- `_load_seen(product_id: str) -> set[str]`
- `_save_seen(product_id: str, seen: set[str]) -> None`
- `_score_posts(posts: list[dict], profile: dict) -> list[dict]`: calls `writer.score_post_for_product` per post.
- `_save_opportunities(product_id: str, opportunities: list[dict]) -> None`: appends to JSONL.
- `ScanResult`: a dataclass or TypedDict with fields: `product_id`, `scanned_at`, `total_fetched`, `new_posts`, `scored`, `opportunities`.

State files:
- `~/.reddit-toolkit/state/{product-id}.seen.json`
- `~/.reddit-toolkit/state/{product-id}.opportunities.jsonl`

---

### `reddit_toolkit/notion_pusher.py`
**Purpose:** All Notion API interactions.

Key functions:
- `get_notion_client() -> notion_client.Client`: reads `NOTION_TOKEN` from env; raises `NotionConfigError` if missing.
- `ensure_database(product_id: str, profile: dict, client) -> str`: creates or retrieves the Notion database ID.
- `push_opportunity(database_id: str, opportunity: dict, client) -> str`: creates a Notion page; returns the page ID.
- `_build_properties(opportunity: dict) -> dict`
- `_build_blocks(opportunity: dict) -> list`
- `_split_text(text: str, max_len: int = 2000) -> list[str]`: splits body text into ≤2000-char chunks for Notion rich text blocks.
- `_load_db_id(product_id: str) -> str | None`
- `_save_db_id(product_id: str, db_id: str) -> None`
- `NotionConfigError(Exception)`

Notion DB ID cache: `~/.reddit-toolkit/notion/{product-id}.notion.json`

---

### `reddit_toolkit/extractor.py`
**Purpose:** Reads files from a directory or single file and concatenates content for profile extraction.

Key functions:
- `read_codebase(path: str, max_chars: int = 8000) -> str`: walks the directory up to depth 3, reads `.py`, `.md`, `.txt`, `.toml`, `.json` files, concatenates with filename headers, truncates at `max_chars`.
- `read_file(path: str, max_chars: int = 8000) -> str`: reads a single file, truncates.
- Skips hidden directories (`.git`, `__pycache__`, `node_modules`, `.venv`).

---

### `reddit_toolkit/writer.py` additions (extend existing file)
New functions to add:

- `extract_profile_from_codebase(text: str) -> dict`: calls Claude; system prompt instructs JSON-only output matching profile schema fields. Returns parsed dict.
- `score_post_for_product(post: dict, profile: dict) -> dict`: calls Claude; returns `{"score": int, "hook_angle": str, "reasoning": str}`.
- `generate_opportunity_draft(post: dict, profile: dict, hook_angle: str) -> dict`: calls Claude; returns `{"title": str, "body": str}`. Increases `max_tokens` to 2048.
- `recommend_subreddits(profile: dict, limit: int = 10) -> list[dict]`: calls Claude; returns list of `{"name": str, "why": str}`.

---

### `reddit_toolkit/cli_product.py`
**Purpose:** Handler functions for the `product` subcommand group, separated from `cli.py` to keep that file manageable.

Functions: `cmd_product_create`, `cmd_product_list`, `cmd_product_show`, `cmd_product_edit`, `cmd_product_add_subreddit`, `cmd_product_recommend_subreddits`.

Imports from: `profile_store`, `writer`, `extractor`, `display`.

---

### `reddit_toolkit/cli_scan.py`
**Purpose:** Handler functions for the `scan` subcommand group.

Functions: `cmd_scan_run`, `cmd_scan_show`, `cmd_scan_setup_cron`.

Imports from: `scanner`, `profile_store`, `display`.

---

### `reddit_toolkit/cli_notion.py`
**Purpose:** Handler functions for the `notion` subcommand group.

Functions: `cmd_notion_setup`, `cmd_notion_push`.

Imports from: `notion_pusher`, `profile_store`.

---

### Test files (new)
- `tests/test_profile_store.py`: tests CRUD operations, `ProfileNotFoundError`, env var override.
- `tests/test_scanner.py`: tests pipeline with mocked `RedditClient` and mocked writer functions; tests seen-deduplication, threshold filtering.
- `tests/test_notion_pusher.py`: tests property/block builders with known inputs; mocks Notion SDK client.
- `tests/test_extractor.py`: tests file reading, depth limit, char truncation, hidden-dir skipping.

---

## New Dependencies

| Package | Version | Why |
|---|---|---|
| `notion-client` | `>=2.2.0` | Official Notion API Python SDK; needed for `notion_pusher.py` |
| `python-dotenv` | `>=1.0.0` | Loads `~/.reddit-toolkit/.env` automatically in cron context where env vars are not set |
| `click` | `>=8.1.0` | **Optional but recommended**: `argparse` nested subcommands become unmanageable at this scale; `click` groups map cleanly onto the `product/scan/notion` command tree. If the team prefers to stay with argparse, this dependency can be omitted and all new commands wired through `build_parser()` instead. |

`requests` and `anthropic` are already present and cover Reddit and AI calls respectively.

No async framework (e.g. `aiohttp`) is needed: the scanner runs sequentially, and the 1-second sleep in `RedditClient` already serializes requests.

---

## Open Questions

1. **One Notion database per product, or one global database?** The spec above creates one database per product. If the user wants to see all products' opportunities in a single Notion view, a `Product` select property could be added and a single shared database used. This needs a decision before implementing `notion_pusher.py`.

2. **Click vs argparse?** The existing codebase uses argparse. Adding three new command groups with multiple subcommands each will make `build_parser()` very long. Migrating to `click` would be cleaner, but breaks the existing structure. Recommendation: stay with argparse if backward compatibility is a priority; switch to click if a full rewrite of `cli.py` is acceptable.

3. **Scan frequency and subreddit volume?** At 1 second per Reddit request and 1 subreddit scanned per trigger, scanning 10 subreddits fetching hot+rising takes ~20 seconds minimum just for Reddit calls. Plus AI scoring at ~1s per post × 35 new posts = ~35 seconds for Claude calls. A full scan for one product with 10 subreddits will take roughly 1–2 minutes. Is this acceptable, or should parallel scanning be designed in from the start?

4. **Reddit `selftext` field?** The current `_normalise_post` in `content.py` (line 8) does not include `selftext` (the post body). For scoring accuracy, the AI should see the post body. The `SAMPLE_POST` in `tests/test_content.py` (line 17) includes `"selftext": ""` suggesting the raw API data has it. Should `_normalise_post` be extended to include `selftext`, or should the scanner fetch a separate detail endpoint per post? Recommendation: add `selftext` to `_normalise_post` (minimal change) rather than an extra API call.

5. **Notion token and parent page ID**: how does the user obtain their Notion integration token and parent page ID? The `notion setup` command should include a short guided prompt or point to a documentation URL. Is there a preferred way to document this for the user?

6. **Opportunity deduplication on re-push**: if `scan run` is run twice in a day (e.g. manual re-run after a config fix), should duplicate opportunities be written to the JSONL and pushed to Notion? The current design uses `seen.json` to prevent re-scoring, so re-runs won't produce duplicates from the Reddit side. But if `notion push --since` is used for backfill, should it check Notion for existing pages? The spec includes a Notion deduplication query, but this adds latency. Needs a decision.

7. **Profile extraction file types**: `extractor.py` reads `.py`, `.md`, `.txt`, `.toml`, `.json`. Should it also read `.yaml`, `.env.example`, `.ts`, `.js`, `.go`, `.rb`, etc.? The right set depends on what kinds of product codebases users will point it at.

8. **Max token budget for AI calls**: `_call_claude` currently uses `max_tokens=1024` (writer.py line 23). Draft generation will need more. Is a hard-coded `max_tokens=2048` for drafts acceptable, or should this be configurable per operation type?
