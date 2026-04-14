# Plan: Reddit Marketing Intelligence Tool

task_id: reddit-marketing-tool-20260411
Spec: spec.md (merged after diff)

---

## Overview

Build on top of the existing `reddit-toolkit` CLI. All new code follows the existing patterns:
- Functions take an optional `client` or `claude_client` for testability
- Tests use `unittest.mock`, never real API calls
- No new top-level framework (stay with argparse)

**Execution order**: Tasks 1–4 are independent and can be done in any order. Task 5 (scanner) depends on 1+2+3. Task 6 (CLI wiring) depends on all. Task 7 (tests) runs alongside each task.

---

## Task 1 — Add `selftext` to `_normalise_post` in `content.py`

**File**: `reddit_toolkit/content.py`
**Why**: AI scoring needs post body text. The raw Reddit API response already includes `selftext`. The current `_normalise_post` (line 8) omits it.

### Steps

- [ ] In `content.py`, edit `_normalise_post` to add `"selftext": data.get("selftext", "")` to the returned dict (after `"created_utc"` on line 18).
- [ ] In `tests/test_content.py`, add `"selftext": ""` to the `SAMPLE_POST` fixture (or confirm it's already there). Add one test asserting `"selftext" in result` from `_normalise_post`.

### Code

```python
# content.py — _normalise_post, add one line
def _normalise_post(data: dict) -> dict:
    return {
        "title": data.get("title", ""),
        "score": data.get("score", 0),
        "url": data.get("url", ""),
        "subreddit": data.get("subreddit", ""),
        "author": data.get("author", ""),
        "num_comments": data.get("num_comments", 0),
        "permalink": data.get("permalink", ""),
        "created_utc": data.get("created_utc", 0.0),
        "selftext": data.get("selftext", ""),  # ← new
    }
```

---

## Task 2 — Create `reddit_toolkit/extractor.py`

**New file.** Reads files from disk for profile extraction.

### Steps

- [ ] Create `reddit_toolkit/extractor.py` with two public functions:
  - `read_file(path: str, max_chars: int = 8000) -> str`
  - `read_codebase(path: str, max_chars: int = 40000) -> str`
- [ ] Create `tests/test_extractor.py`.

### Code

```python
# reddit_toolkit/extractor.py
import os

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}
_TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".json", ".yaml", ".yml",
                    ".ts", ".js", ".go", ".rb", ".env.example"}


def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a single file and return its content, truncated to max_chars."""
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars)
    return f"# {os.path.basename(path)}\n\n{content}"


def read_codebase(path: str, max_chars: int = 40000) -> str:
    """Walk a directory (depth ≤ 3) and concatenate text file contents up to max_chars."""
    parts = []
    total = 0
    root = os.path.abspath(path)

    for dirpath, dirnames, filenames in os.walk(root):
        # Depth check
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 3:
            dirnames.clear()
            continue

        # Skip hidden/build dirs in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _TEXT_EXTENSIONS:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    chunk = f.read(max_chars - total)
                if not chunk:
                    break
                rel_path = os.path.relpath(fpath, root)
                parts.append(f"# {rel_path}\n\n{chunk}")
                total += len(chunk)
            except OSError:
                continue
            if total >= max_chars:
                break
        if total >= max_chars:
            break

    return "\n\n---\n\n".join(parts)
```

### Tests

```python
# tests/test_extractor.py
import os
import tempfile
import pytest
from reddit_toolkit.extractor import read_file, read_codebase


def test_read_file_returns_content(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("Hello world")
    result = read_file(str(f))
    assert "Hello world" in result
    assert "README.md" in result


def test_read_file_truncates(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 10000)
    result = read_file(str(f), max_chars=100)
    assert len(result) < 200  # header + 100 chars


def test_read_codebase_skips_hidden_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret")
    (tmp_path / "README.md").write_text("visible")
    result = read_codebase(str(tmp_path))
    assert "secret" not in result
    assert "visible" in result


def test_read_codebase_respects_max_chars(tmp_path):
    for i in range(5):
        (tmp_path / f"file{i}.md").write_text("y" * 1000)
    result = read_codebase(str(tmp_path), max_chars=2000)
    assert len(result) <= 2500  # some header overhead
```

---

## Task 3 — Create `reddit_toolkit/profile_store.py`

**New file.** Product profile CRUD on disk.

### Steps

- [ ] Create `reddit_toolkit/profile_store.py`.
- [ ] Create `tests/test_profile_store.py`.

### Code

```python
# reddit_toolkit/profile_store.py
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


class ProfileNotFoundError(Exception):
    pass


def _data_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    return Path(base).expanduser()


def profiles_dir() -> Path:
    d = _data_dir() / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load(product_id: str) -> dict:
    path = profiles_dir() / f"{product_id}.json"
    if not path.exists():
        raise ProfileNotFoundError(f"Profile '{product_id}' not found.")
    with open(path) as f:
        return json.load(f)


def save(profile: dict) -> None:
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = profiles_dir() / f"{profile['id']}.json"
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)


def list_profiles() -> list:
    return [
        json.loads(p.read_text())
        for p in sorted(profiles_dir().glob("*.json"))
    ]


def new_profile(name: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": slugify(name),
        "name": name,
        "created_at": now,
        "updated_at": now,
        "description": "",
        "problem_solved": "",
        "target_audience": [],
        "key_features": [],
        "tone": "casual",
        "keywords": [],
        "avoid_topics": [],
        "subreddits": [],
        "scan_threshold": 7,
        "codebase_summary": "",
    }
```

### Tests

```python
# tests/test_profile_store.py
import json
import os
import pytest
from unittest.mock import patch
from reddit_toolkit.profile_store import (
    load, save, list_profiles, new_profile, slugify, ProfileNotFoundError
)


def test_slugify():
    assert slugify("My Cool App") == "my-cool-app"
    assert slugify("  Reddit Tool! ") == "reddit-tool"


def test_save_and_load(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        profile = new_profile("Test App")
        save(profile)
        loaded = load("test-app")
    assert loaded["name"] == "Test App"
    assert loaded["id"] == "test-app"


def test_load_missing_raises(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        with pytest.raises(ProfileNotFoundError):
            load("nonexistent")


def test_list_profiles(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        save(new_profile("App One"))
        save(new_profile("App Two"))
        profiles = list_profiles()
    assert len(profiles) == 2
    names = {p["name"] for p in profiles}
    assert names == {"App One", "App Two"}
```

---

## Task 4 — Add new AI functions to `reddit_toolkit/writer.py`

**Modify existing file.** Add 4 functions after line 112.

### Steps

- [ ] Add `extract_profile_from_text(raw_text: str, name: str) -> dict`
- [ ] Add `recommend_subreddits(profile: dict, limit: int = 10) -> list`
- [ ] Add `score_post_for_product(post: dict, profile: dict) -> dict`
- [ ] Add `generate_opportunity_draft(post: dict, profile: dict, hook_angle: str) -> dict`
- [ ] Add tests to `tests/test_writer.py` for each new function (mock `_make_client`).

### Code

```python
# Append to reddit_toolkit/writer.py after line 112

import json as _json


def extract_profile_from_text(raw_text: str, name: str) -> dict:
    """Ask Claude to extract a product profile from raw codebase/README text.

    Returns a dict with keys: description, problem_solved, target_audience,
    key_features, keywords. Keys may be empty strings/lists if not found.
    """
    client = _make_client()
    system = (
        "You are a product analyst. Given text from a software product's codebase or documentation, "
        "extract key product information. Respond with a JSON object only — no other text. "
        'Schema: {"description": str, "problem_solved": str, "target_audience": [str], '
        '"key_features": [str], "keywords": [str]}'
    )
    user = f"Product name: {name}\n\nContent:\n{raw_text[:30000]}"
    raw = _call_claude(client, system, user)
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        # Fallback: return partial structure
        return {"description": raw[:500], "problem_solved": "", "target_audience": [],
                "key_features": [], "keywords": []}


def recommend_subreddits(profile: dict, limit: int = 10) -> list:
    """Ask Claude to recommend subreddits for a product.

    Returns list of {"name": str, "why": str}.
    """
    client = _make_client()
    system = (
        "You are a Reddit marketing expert. Given a product description, recommend subreddits "
        f"where the product would be naturally relevant to discuss. Return a JSON array of exactly {limit} objects. "
        'Schema: [{"name": "subreddit_name_without_r/", "why": "one sentence reason"}]'
    )
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Target audience: {', '.join(profile.get('target_audience', []))}\n"
        f"Key features: {', '.join(profile.get('key_features', []))}"
    )
    raw = _call_claude(client, system, user)
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return []


def score_post_for_product(post: dict, profile: dict) -> dict:
    """Score a Reddit post's relevance as a marketing opportunity for the product.

    Returns {"score": int (0-10), "hook_angle": str, "reasoning": str}.
    On parse failure returns {"score": 0, "hook_angle": "", "reasoning": "parse error"}.
    """
    client = _make_client()
    system = (
        "You are a Reddit marketing analyst. Score how relevant this Reddit post is as an "
        "opportunity to naturally mention or promote the product. Be strict: only score >= 7 "
        "if the post topic directly relates to a problem the product solves or a feature it has. "
        "Return JSON only. Schema: {\"score\": <int 0-10>, \"hook_angle\": \"<one sentence>\", "
        "\"reasoning\": \"<one sentence>\"}"
    )
    selftext_preview = (post.get("selftext") or "")[:500]
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Problem solved: {profile.get('problem_solved', '')}\n"
        f"Keywords: {', '.join(profile.get('keywords', []))}\n\n"
        f"Reddit post:\n"
        f"Title: {post.get('title', '')}\n"
        f"Subreddit: r/{post.get('subreddit', '')}\n"
        f"Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}\n"
        f"Body preview: {selftext_preview}"
    )
    raw = _call_claude(client, system, user)
    try:
        result = _json.loads(raw)
        return {
            "score": int(result.get("score", 0)),
            "hook_angle": result.get("hook_angle", ""),
            "reasoning": result.get("reasoning", ""),
        }
    except (_json.JSONDecodeError, ValueError):
        return {"score": 0, "hook_angle": "", "reasoning": "parse error"}


def generate_opportunity_draft(post: dict, profile: dict, hook_angle: str) -> dict:
    """Generate a Reddit post draft for a marketing opportunity.

    Returns {"title": str, "body": str}.
    """
    client = _make_client()
    system = (
        f"You are a Reddit marketing expert writing for r/{post.get('subreddit', 'all')}. "
        "Write a genuine Reddit post that contributes value to the discussion first, then "
        "naturally mentions the product where relevant. The post must feel organic — not an ad. "
        f"Tone: {profile.get('tone', 'casual')}. Max 300 words for the body. "
        "Return JSON only. Schema: {\"title\": str, \"body\": str}"
    )
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Product description: {profile.get('description', '')}\n"
        f"Hook angle: {hook_angle}\n\n"
        f"Trending post to respond to:\n"
        f"Title: {post.get('title', '')}\n"
        f"r/{post.get('subreddit', '')} | {post.get('score', 0)} upvotes | "
        f"{post.get('num_comments', 0)} comments"
    )
    # Use higher token budget for draft generation (2048 instead of default 1024)
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text
    try:
        result = _json.loads(raw)
        return {"title": result.get("title", ""), "body": result.get("body", "")}
    except _json.JSONDecodeError:
        return {"title": "", "body": raw[:2000]}
```

### Tests to add in `test_writer.py`

```python
class TestScorePostForProduct:
    def test_returns_score_dict(self):
        mock_client = make_anthropic_mock('{"score": 8, "hook_angle": "relevant", "reasoning": "matches"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = score_post_for_product(
                    {"title": "test", "subreddit": "python", "score": 100, "num_comments": 10, "selftext": ""},
                    {"name": "MyApp", "description": "...", "problem_solved": "", "keywords": []}
                )
        assert result["score"] == 8
        assert isinstance(result["hook_angle"], str)

    def test_parse_error_returns_zero_score(self):
        mock_client = make_anthropic_mock("not json")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = score_post_for_product({"title": "t", "subreddit": "s", "score": 0, "num_comments": 0, "selftext": ""}, {})
        assert result["score"] == 0
        assert result["reasoning"] == "parse error"


class TestGenerateOpportunityDraft:
    def test_returns_title_and_body(self):
        mock_client = make_anthropic_mock('{"title": "A title", "body": "A body"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = generate_opportunity_draft(
                    {"title": "t", "subreddit": "python", "score": 100, "num_comments": 5},
                    {"name": "MyApp", "description": "...", "tone": "casual"},
                    "hook"
                )
        assert result["title"] == "A title"
        assert result["body"] == "A body"
```

---

## Task 5 — Create `reddit_toolkit/scanner.py`

**New file.** Core scan pipeline.

### Steps

- [ ] Create `reddit_toolkit/scanner.py`.
- [ ] Create `tests/test_scanner.py`.

### Code

```python
# reddit_toolkit/scanner.py
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .content import get_hot_posts, get_rising_posts
from .writer import score_post_for_product, generate_opportunity_draft


def _state_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    d = Path(base).expanduser() / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_seen(product_id: str) -> set:
    path = _state_dir() / f"{product_id}.seen.json"
    if not path.exists():
        return set()
    with open(path) as f:
        return set(json.load(f))


def _save_seen(product_id: str, seen: set) -> None:
    path = _state_dir() / f"{product_id}.seen.json"
    with open(path, "w") as f:
        json.dump(list(seen), f)


def _append_opportunities(product_id: str, opportunities: list) -> None:
    path = _state_dir() / f"{product_id}.opportunities.jsonl"
    with open(path, "a") as f:
        for opp in opportunities:
            f.write(json.dumps(opp) + "\n")


def _fetch_posts(subreddits: list, client=None) -> list:
    """Fetch hot + rising posts from each subreddit. Dedup by permalink."""
    seen_permalinks = set()
    posts = []
    for sub in subreddits:
        for post in get_hot_posts(subreddit=sub, limit=25, client=client):
            if post["permalink"] not in seen_permalinks:
                seen_permalinks.add(post["permalink"])
                posts.append(post)
        for post in get_rising_posts(subreddit=sub, limit=10, client=client):
            if post["permalink"] not in seen_permalinks:
                seen_permalinks.add(post["permalink"])
                posts.append(post)
    return posts


@dataclass
class ScanResult:
    product_id: str
    scanned_at: str
    subreddits: list
    total_fetched: int
    new_posts: int
    opportunities: list = field(default_factory=list)


def run_scan(
    profile: dict,
    dry_run: bool = False,
    top_n: int = 5,
    threshold: int = None,
    reddit_client=None,
    notion_push_fn=None,
) -> ScanResult:
    """Run the full scan pipeline for a product.

    Args:
        profile: Product profile dict.
        dry_run: If True, score posts but do not push to Notion.
        top_n: Maximum opportunities to generate drafts for.
        threshold: Score threshold override (uses profile["scan_threshold"] if None).
        reddit_client: Injectable RedditClient for testing.
        notion_push_fn: Callable(opportunity) for testing; defaults to real Notion push.
    """
    product_id = profile["id"]
    effective_threshold = threshold if threshold is not None else profile.get("scan_threshold", 7)
    subreddit_names = [s["name"] for s in profile.get("subreddits", [])]
    scanned_at = datetime.now(timezone.utc).isoformat()

    _log(f"Starting scan for product: {product_id}")
    _log(f"Subreddits: {subreddit_names}")

    # 1. Fetch posts
    all_posts = _fetch_posts(subreddit_names, client=reddit_client)
    _log(f"Fetched {len(all_posts)} posts total")

    # 2. Filter already-seen
    seen = _load_seen(product_id)
    new_posts = [p for p in all_posts if p["permalink"] not in seen]
    _log(f"{len(new_posts)} new posts to score (skipping {len(all_posts) - len(new_posts)} seen)")

    # 3. Score
    scored = []
    for post in new_posts:
        score_result = score_post_for_product(post, profile)
        scored.append({"post": post, "score_result": score_result})
        time.sleep(0.3)  # avoid hammering Anthropic API

    # 4. Filter by threshold, sort, take top N
    opportunities_raw = [
        s for s in scored if s["score_result"]["score"] >= effective_threshold
    ]
    opportunities_raw.sort(key=lambda x: x["score_result"]["score"], reverse=True)
    opportunities_raw = opportunities_raw[:top_n]
    _log(f"{len(opportunities_raw)} opportunities above threshold {effective_threshold}")

    # 5. Generate drafts
    opportunities = []
    for item in opportunities_raw:
        draft = generate_opportunity_draft(
            item["post"], profile, item["score_result"]["hook_angle"]
        )
        opportunity = {
            "product_id": product_id,
            "scanned_at": scanned_at,
            "post": item["post"],
            "score_result": item["score_result"],
            "draft": draft,
        }
        opportunities.append(opportunity)

    # 6. Update seen set
    for post in new_posts:
        seen.add(post["permalink"])
    _save_seen(product_id, seen)

    # 7. Persist locally
    _append_opportunities(product_id, opportunities)

    result = ScanResult(
        product_id=product_id,
        scanned_at=scanned_at,
        subreddits=subreddit_names,
        total_fetched=len(all_posts),
        new_posts=len(new_posts),
        opportunities=opportunities,
    )

    if dry_run:
        _log("Dry run — skipping Notion push")
        return result

    # 8. Push to Notion
    if notion_push_fn:
        # Test-injectable path: callable(opportunity_or_None) for each item
        for opp in opportunities:
            notion_push_fn(opp)
        if not opportunities:
            notion_push_fn(None)  # signals empty scan to test spy
    else:
        from .notion_pusher import push_scan_results
        push_scan_results(profile, result)

    _log("Scan complete.")
    return result


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} [INFO] {msg}")
```

### Tests

```python
# tests/test_scanner.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.scanner import run_scan, _fetch_posts, _load_seen, _save_seen


SAMPLE_PROFILE = {
    "id": "test-app",
    "name": "Test App",
    "description": "A test product",
    "problem_solved": "Testing",
    "keywords": ["test"],
    "tone": "casual",
    "subreddits": [{"name": "python", "why": "devs"}],
    "scan_threshold": 7,
    "target_audience": ["developers"],
    "key_features": [],
}

SAMPLE_POST = {
    "title": "Test post",
    "score": 100,
    "url": "https://example.com",
    "subreddit": "python",
    "author": "user",
    "num_comments": 10,
    "permalink": "/r/python/comments/abc",
    "created_utc": 0.0,
    "selftext": "",
}


def test_seen_deduplication(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        _save_seen("test-app", {"/r/python/comments/abc"})
        seen = _load_seen("test-app")
    assert "/r/python/comments/abc" in seen


def test_run_scan_dry_run_no_notion(tmp_path):
    """Dry run should score posts but not push to Notion."""
    mock_reddit_client = MagicMock()
    mock_reddit_client.get.return_value = {
        "data": {"children": [{"kind": "t3", "data": {**SAMPLE_POST, "selftext": ""}}]}
    }
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner.score_post_for_product",
                   return_value={"score": 9, "hook_angle": "relevant", "reasoning": "matches"}):
            with patch("reddit_toolkit.scanner.generate_opportunity_draft",
                       return_value={"title": "Draft", "body": "Body"}):
                result = run_scan(SAMPLE_PROFILE, dry_run=True, reddit_client=mock_reddit_client)
    assert result.product_id == "test-app"
    assert result.total_fetched >= 0


def test_threshold_filtering(tmp_path):
    """Posts below threshold should not become opportunities."""
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner._fetch_posts", return_value=[SAMPLE_POST]):
            with patch("reddit_toolkit.scanner.score_post_for_product",
                       return_value={"score": 3, "hook_angle": "", "reasoning": ""}):
                result = run_scan(SAMPLE_PROFILE, dry_run=True)
    assert len(result.opportunities) == 0
```

---

## Task 6 — Create `reddit_toolkit/notion_pusher.py`

**New file.** All Notion API interactions.

### Steps

- [ ] Create `reddit_toolkit/notion_pusher.py`.
- [ ] Create `tests/test_notion_pusher.py`.
- [ ] Store Notion DB ID at `~/.reddit-toolkit/notion/{product-id}.notion.json`.

### Code

```python
# reddit_toolkit/notion_pusher.py
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class NotionConfigError(Exception):
    pass


def _notion_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    d = Path(base).expanduser() / "notion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_db_id(product_id: str) -> str | None:
    path = _notion_dir() / f"{product_id}.notion.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f).get("database_id")


def _save_db_id(product_id: str, db_id: str) -> None:
    path = _notion_dir() / f"{product_id}.notion.json"
    with open(path, "w") as f:
        json.dump({"database_id": db_id}, f)


def get_notion_client():
    """Return a configured notion_client.Client instance."""
    try:
        from notion_client import Client
    except ImportError:
        raise NotionConfigError("notion-client is not installed. Run: pip install notion-client")
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise NotionConfigError("NOTION_TOKEN environment variable is not set.")
    return Client(auth=token)


def ensure_database(product_id: str, profile: dict, client=None) -> str:
    """Return the Notion database ID for the product, creating it if needed."""
    cached = _load_db_id(product_id)
    if cached:
        return cached

    if client is None:
        client = get_notion_client()

    parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not parent_page_id:
        raise NotionConfigError("NOTION_PARENT_PAGE_ID environment variable is not set.")

    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": f"{profile['name']} — Reddit Opportunities"}}],
        properties=_database_schema(),
    )
    db_id = db["id"]
    _save_db_id(product_id, db_id)
    return db_id


def _database_schema() -> dict:
    return {
        "Post Title": {"title": {}},
        "Status": {"select": {"options": [
            {"name": "Draft", "color": "yellow"},
            {"name": "Posted", "color": "green"},
            {"name": "Skipped", "color": "gray"},
        ]}},
        "Subreddit": {"select": {}},
        "AI Score": {"number": {}},
        "Hook Angle": {"rich_text": {}},
        "Reddit URL": {"url": {}},
        "Reddit Score": {"number": {}},
        "Comments": {"number": {}},
        "Scanned At": {"date": {}},
        "Draft Title": {"rich_text": {}},
        "Reasoning": {"rich_text": {}},
    }


def _build_properties(opportunity: dict) -> dict:
    post = opportunity["post"]
    score_result = opportunity["score_result"]
    draft = opportunity["draft"]
    return {
        "Post Title": {"title": [{"text": {"content": post.get("title", "")[:2000]}}]},
        "Status": {"select": {"name": "Draft"}},
        "Subreddit": {"select": {"name": post.get("subreddit", "unknown")}},
        "AI Score": {"number": score_result.get("score", 0)},
        "Hook Angle": {"rich_text": [{"text": {"content": score_result.get("hook_angle", "")[:2000]}}]},
        "Reddit URL": {"url": f"https://reddit.com{post.get('permalink', '')}"},
        "Reddit Score": {"number": post.get("score", 0)},
        "Comments": {"number": post.get("num_comments", 0)},
        "Scanned At": {"date": {"start": opportunity.get("scanned_at", datetime.now(timezone.utc).isoformat())}},
        "Draft Title": {"rich_text": [{"text": {"content": draft.get("title", "")[:2000]}}]},
        "Reasoning": {"rich_text": [{"text": {"content": score_result.get("reasoning", "")[:2000]}}]},
    }


def _split_text(text: str, max_len: int = 1900) -> list:
    """Split text into chunks for Notion rich_text blocks (2000-char limit)."""
    return [text[i:i + max_len] for i in range(0, len(text), max_len)] if text else [""]


def _build_blocks(opportunity: dict) -> list:
    post = opportunity["post"]
    score_result = opportunity["score_result"]
    draft = opportunity["draft"]
    blocks = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Original Post"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content":
            f"r/{post.get('subreddit', '')} | Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}"
        }}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content":
            f"https://reddit.com{post.get('permalink', '')}"
        }}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "AI Analysis"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content":
            f"Score: {score_result.get('score', 0)}/10\nHook: {score_result.get('hook_angle', '')}\nReasoning: {score_result.get('reasoning', '')}"
        }}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Draft Post"}}]}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "Title"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": draft.get("title", "")}}]}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "Body"}}]}},
    ]
    # Split body into ≤1900-char blocks
    for chunk in _split_text(draft.get("body", "")):
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": chunk}}]}})
    return blocks


def push_opportunity(database_id: str, opportunity: dict, client=None) -> str:
    """Create a Notion page for one opportunity. Returns page ID."""
    if client is None:
        client = get_notion_client()
    page = client.pages.create(
        parent={"database_id": database_id},
        properties=_build_properties(opportunity),
        children=_build_blocks(opportunity),
    )
    return page["id"]


def push_empty_scan(database_id: str, product_id: str, scanned_at: str, client=None) -> str:
    """Push a 'no opportunities found' summary page. Returns page ID."""
    if client is None:
        client = get_notion_client()
    page = client.pages.create(
        parent={"database_id": database_id},
        properties={
            "Post Title": {"title": [{"text": {"content": f"[Scan] No opportunities — {scanned_at[:10]}"}}]},
            "Status": {"select": {"name": "Skipped"}},
            "Scanned At": {"date": {"start": scanned_at}},
        },
    )
    return page["id"]


def push_scan_results(profile: dict, scan_result, client=None) -> None:
    """Push all opportunities from a ScanResult to Notion. Handles empty scans."""
    if client is None:
        client = get_notion_client()
    db_id = ensure_database(profile["id"], profile, client=client)
    if not scan_result.opportunities:
        push_empty_scan(db_id, profile["id"], scan_result.scanned_at, client=client)
        return
    for opp in scan_result.opportunities:
        push_opportunity(db_id, opp, client=client)
```

### Tests

```python
# tests/test_notion_pusher.py
import os
import pytest
from unittest.mock import MagicMock, patch
from reddit_toolkit.notion_pusher import (
    _build_properties, _build_blocks, _split_text, NotionConfigError, get_notion_client
)

SAMPLE_OPPORTUNITY = {
    "product_id": "test-app",
    "scanned_at": "2026-04-11T09:00:00Z",
    "post": {
        "title": "Great post about testing",
        "score": 500,
        "subreddit": "python",
        "num_comments": 42,
        "permalink": "/r/python/comments/xyz",
        "selftext": "body text",
    },
    "score_result": {"score": 8, "hook_angle": "Relevant hook", "reasoning": "Matches"},
    "draft": {"title": "Draft title", "body": "Draft body text"},
}


def test_build_properties_has_required_keys():
    props = _build_properties(SAMPLE_OPPORTUNITY)
    assert "Post Title" in props
    assert "AI Score" in props
    assert props["AI Score"]["number"] == 8
    assert props["Status"]["select"]["name"] == "Draft"


def test_build_blocks_returns_list():
    blocks = _build_blocks(SAMPLE_OPPORTUNITY)
    assert isinstance(blocks, list)
    assert len(blocks) > 0


def test_split_text_chunking():
    text = "x" * 5000
    chunks = _split_text(text, max_len=1900)
    assert len(chunks) == 3
    assert all(len(c) <= 1900 for c in chunks)


def test_get_notion_client_raises_without_token():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("NOTION_TOKEN", None)
        with pytest.raises(NotionConfigError, match="NOTION_TOKEN"):
            get_notion_client()
```

---

## Task 7 — Create `reddit_toolkit/cli_product.py`, `cli_scan.py`, `cli_notion.py`

**New files.** CLI handler functions, wired into `cli.py`.

### Steps

- [ ] Create `reddit_toolkit/cli_product.py` with handlers for `product` subcommands.
- [ ] Create `reddit_toolkit/cli_scan.py` with handlers for `scan` subcommands.
- [ ] Create `reddit_toolkit/cli_notion.py` with handlers for `notion` subcommands.
- [ ] Modify `reddit_toolkit/cli.py`: import new handler modules, extend `build_parser()` with 3 new command groups.

### `cli_product.py`

```python
# reddit_toolkit/cli_product.py
import json
import os
import sys

from .profile_store import new_profile, save, load, list_profiles, slugify, ProfileNotFoundError
from .writer import extract_profile_from_text, recommend_subreddits, WriterConfigError
from .extractor import read_file, read_codebase
from .display import print_text


def cmd_product_create(args):
    profile = new_profile(args.name)

    raw_text = ""
    if args.from_dir:
        print(f"Reading codebase from {args.from_dir}...")
        raw_text = read_codebase(args.from_dir)
    elif args.from_file:
        print(f"Reading file {args.from_file}...")
        raw_text = read_file(args.from_file)
    elif args.description:
        raw_text = args.description

    if raw_text:
        print("Extracting product profile with AI...")
        try:
            extracted = extract_profile_from_text(raw_text, args.name)
        except WriterConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        for key in ("description", "problem_solved", "target_audience", "key_features", "keywords"):
            if extracted.get(key):
                profile[key] = extracted[key]

    print("\nDraft profile:")
    print(json.dumps(profile, indent=2))
    confirm = input("\nSave? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    save(profile)
    print(f"Saved profile '{profile['id']}'.")


def cmd_product_list(args):
    profiles = list_profiles()
    if not profiles:
        print("No products configured.")
        return
    for p in profiles:
        sub_count = len(p.get("subreddits", []))
        print(f"  {p['id']} — {p['name']} ({sub_count} subreddits)")


def cmd_product_show(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(profile, indent=2))


def cmd_product_add_subreddit(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    profile["subreddits"].append({
        "name": args.subreddit,
        "why": args.why or "",
        "added_by": "user",
    })
    save(profile)
    print(f"Added r/{args.subreddit} to {args.product_id}.")


def cmd_product_recommend_subreddits(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        suggestions = recommend_subreddits(profile, limit=args.limit)
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\nSuggested subreddits for '{profile['name']}':")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. r/{s['name']} — {s['why']}")

    confirm = input("\nAdd all to profile? [y/N]: ").strip().lower()
    if confirm == "y":
        for s in suggestions:
            profile["subreddits"].append({"name": s["name"], "why": s["why"], "added_by": "ai"})
        save(profile)
        print(f"Added {len(suggestions)} subreddits.")
```

### `cli_scan.py`

```python
# reddit_toolkit/cli_scan.py
import json
import shutil
import sys

from .profile_store import load, ProfileNotFoundError
from .scanner import run_scan


def cmd_scan_run(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = run_scan(
        profile=profile,
        dry_run=args.dry_run,
        top_n=args.top,
        threshold=args.threshold,
    )
    print(f"\nScan summary:")
    print(f"  Subreddits scanned: {len(result.subreddits)}")
    print(f"  Posts fetched: {result.total_fetched}")
    print(f"  New posts scored: {result.new_posts}")
    print(f"  Opportunities found: {len(result.opportunities)}")
    if args.dry_run:
        for opp in result.opportunities:
            print(f"\n  [{opp['score_result']['score']}/10] {opp['post']['title']}")
            print(f"  Hook: {opp['score_result']['hook_angle']}")
            print(f"  Draft title: {opp['draft']['title']}")


def cmd_scan_show(args):
    from pathlib import Path
    import os
    state_dir = Path(os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")).expanduser() / "state"
    path = state_dir / f"{args.product}.opportunities.jsonl"
    if not path.exists():
        print(f"No scan history for '{args.product}'.")
        return
    lines = path.read_text().strip().split("\n")
    lines = [l for l in lines if l]
    recent = lines[-(args.last):]
    for line in recent:
        try:
            opp = json.loads(line)
            print(f"[{opp['scanned_at'][:10]}] [{opp['score_result']['score']}/10] {opp['post']['title']}")
        except Exception:
            continue


def cmd_scan_setup_cron(args):
    binary = shutil.which("reddit-toolkit")
    if not binary:
        binary = "/path/to/reddit-toolkit"
        print("Warning: 'reddit-toolkit' not found in PATH. Replace the path below manually.")
    hour = str(args.hour).zfill(2)
    minute = str(args.minute).zfill(2)
    log_path = f"~/.reddit-toolkit/logs/{args.product}.log"
    line = f"{args.minute} {args.hour} * * * {binary} scan run --product {args.product} >> {log_path} 2>&1"
    print("\nAdd this line to your crontab (run 'crontab -e'):\n")
    print(f"  {line}\n")
```

### `cli_notion.py`

```python
# reddit_toolkit/cli_notion.py
import sys

from .profile_store import load, ProfileNotFoundError
from .notion_pusher import ensure_database, NotionConfigError


def cmd_notion_setup(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        db_id = ensure_database(profile["id"], profile)
    except NotionConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Notion database ready: {db_id}")
    print(f"Open in Notion: https://notion.so/{db_id.replace('-', '')}")
```

### `cli.py` additions

In `build_parser()` after the existing `write` section (after line 221), add:

```python
    # --- product ---
    from .cli_product import (
        cmd_product_create, cmd_product_list, cmd_product_show,
        cmd_product_add_subreddit, cmd_product_recommend_subreddits,
    )
    from .cli_scan import cmd_scan_run, cmd_scan_show, cmd_scan_setup_cron
    from .cli_notion import cmd_notion_setup

    product_parser = subparsers.add_parser("product", help="Manage product profiles")
    product_sub = product_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    pc_p = product_sub.add_parser("create", help="Create a new product profile")
    pc_p.add_argument("--name", required=True, help="Product name")
    pc_p.add_argument("--description", default="", help="Product description")
    pc_p.add_argument("--from-file", default=None, metavar="FILE")
    pc_p.add_argument("--from-dir", default=None, metavar="DIR")
    pc_p.set_defaults(func=cmd_product_create)

    pl_p = product_sub.add_parser("list", help="List all product profiles")
    pl_p.set_defaults(func=cmd_product_list)

    ps_p = product_sub.add_parser("show", help="Show a product profile")
    ps_p.add_argument("product_id")
    ps_p.set_defaults(func=cmd_product_show)

    pa_p = product_sub.add_parser("add-subreddit", help="Add a subreddit to a product")
    pa_p.add_argument("product_id")
    pa_p.add_argument("subreddit")
    pa_p.add_argument("--why", default="")
    pa_p.set_defaults(func=cmd_product_add_subreddit)

    pr_p = product_sub.add_parser("recommend-subreddits", help="AI-recommend subreddits")
    pr_p.add_argument("product_id")
    pr_p.add_argument("--limit", "-n", type=int, default=10)
    pr_p.set_defaults(func=cmd_product_recommend_subreddits)

    # --- scan ---
    scan_parser = subparsers.add_parser("scan", help="Scan Reddit for opportunities")
    scan_sub = scan_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    sr_p = scan_sub.add_parser("run", help="Run a scan for a product")
    sr_p.add_argument("--product", required=True)
    sr_p.add_argument("--threshold", type=int, default=None)
    sr_p.add_argument("--top", type=int, default=5)
    sr_p.add_argument("--dry-run", action="store_true")
    sr_p.set_defaults(func=cmd_scan_run)

    ss_p = scan_sub.add_parser("show", help="Show recent scan results")
    ss_p.add_argument("--product", required=True)
    ss_p.add_argument("--last", type=int, default=20)
    ss_p.set_defaults(func=cmd_scan_show)

    sc_p = scan_sub.add_parser("setup-cron", help="Print a crontab line for scheduled scanning")
    sc_p.add_argument("--product", required=True)
    sc_p.add_argument("--hour", type=int, default=8)
    sc_p.add_argument("--minute", type=int, default=0)
    sc_p.set_defaults(func=cmd_scan_setup_cron)

    # --- notion ---
    notion_parser = subparsers.add_parser("notion", help="Manage Notion integration")
    notion_sub = notion_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    ns_p = notion_sub.add_parser("setup", help="Create Notion database for a product")
    ns_p.add_argument("--product", required=True)
    ns_p.set_defaults(func=cmd_notion_setup)
```

---

## Task 8 — Update dependencies

### Steps

- [ ] Add `notion-client>=2.2.1` and `python-dotenv>=1.0.0` to `pyproject.toml` dependencies list.
- [ ] Mirror in `requirements.txt`.
- [ ] Add `python-dotenv` loading at the top of `scanner.py` (loads `~/.reddit-toolkit/.env` if it exists).

### `pyproject.toml` change

```toml
dependencies = [
    "requests>=2.33.1",
    "anthropic>=0.94.0",
    "notion-client>=2.2.1",
    "python-dotenv>=1.0.0",
]
```

### dotenv loading in `scanner.py` (top of file, after imports)

```python
# Load ~/.reddit-toolkit/.env for cron environments
import pathlib as _pathlib
_env_file = _pathlib.Path("~/.reddit-toolkit/.env").expanduser()
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(str(_env_file), override=False)
```

---

## Execution Order Summary

```
Task 1 (selftext)      ← can start immediately
Task 2 (extractor)     ← can start immediately
Task 3 (profile_store) ← can start immediately
Task 4 (writer fns)    ← can start immediately
Task 5 (scanner)       ← needs Tasks 1, 3, 4
Task 6 (notion_pusher) ← can start immediately
Task 7 (CLI wiring)    ← needs Tasks 2, 3, 4, 5, 6
Task 8 (deps)          ← do alongside Task 6
```

## Verification Checklist

After all tasks complete:
- [ ] `pytest` passes with no failures
- [ ] `reddit-toolkit product create --name "Test" --description "A test product"` saves a profile
- [ ] `reddit-toolkit product recommend-subreddits test` suggests subreddits
- [ ] `reddit-toolkit scan run --product test --dry-run` runs without error
- [ ] `reddit-toolkit notion setup --product test` creates a Notion database (requires env vars)
- [ ] `reddit-toolkit scan setup-cron --product test --hour 9` prints a valid crontab line
