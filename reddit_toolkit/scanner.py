# reddit_toolkit/scanner.py
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .content import get_hot_posts, get_rising_posts
from .writer import score_post_for_product, generate_opportunity_draft

# Load ~/.reddit-toolkit/.env for cron environments
_env_file = Path("~/.reddit-toolkit/.env").expanduser()
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(str(_env_file), override=False)


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
    """Run the full scan pipeline for a product."""
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
        time.sleep(0.3)

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
        for opp in opportunities:
            notion_push_fn(opp)
        if not opportunities:
            notion_push_fn(None)
    else:
        from .notion_pusher import push_scan_results
        push_scan_results(profile, result)

    _log("Scan complete.")
    return result


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} [INFO] {msg}")
