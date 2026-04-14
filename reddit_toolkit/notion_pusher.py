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


def link_database(product_id: str, database_id: str, client=None) -> None:
    """Save an existing Notion database ID for a product and ensure its schema."""
    _save_db_id(product_id, database_id)
    if client is None:
        client = get_notion_client()
    ensure_schema(database_id, client)


def ensure_schema(database_id: str, client=None) -> None:
    """Add any missing properties to an existing Notion database."""
    if client is None:
        client = get_notion_client()
    schema = _database_schema()
    # Title column already exists as "Name"; skip it and add the rest
    props_to_add = {k: v for k, v in schema.items() if k != "Name"}
    client.databases.update(database_id, properties=props_to_add)


def ensure_database(product_id: str, profile: dict, client=None) -> str:
    """Return the Notion database ID for the product, creating it if needed."""
    cached = _load_db_id(product_id)
    if cached:
        return cached

    if client is None:
        client = get_notion_client()

    parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID")
    if not parent_page_id:
        raise NotionConfigError(
            "NOTION_PARENT_PAGE_ID environment variable is not set.\n"
            "Tip: use 'notion setup --product <id> --database-id <id>' to link an existing database."
        )

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
        "Name": {"title": {}},
        "Type": {"select": {"options": [
            {"name": "Post", "color": "blue"},
            {"name": "Comment", "color": "purple"},
        ]}},
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
        "Comment": {"number": {}},
        "Scanned At": {"date": {}},
        "Draft Title": {"rich_text": {}},
        "Reasoning": {"rich_text": {}},
    }


def _build_properties(opportunity: dict) -> dict:
    post = opportunity["post"]
    score_result = opportunity["score_result"]
    draft = opportunity["draft"]
    return {
        "Name": {"title": [{"text": {"content": post.get("title", "")[:2000]}}]},
        "Type": {"select": {"name": "Comment"}},
        "Status": {"select": {"name": "Draft"}},
        "Subreddit": {"select": {"name": post.get("subreddit", "unknown")}},
        "AI Score": {"number": score_result.get("score", 0)},
        "Hook Angle": {"rich_text": [{"text": {"content": score_result.get("hook_angle", "")[:2000]}}]},
        "Reddit URL": {"url": post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}"},
        "Reddit Score": {"number": post.get("score", 0)},
        "Comment": {"number": post.get("num_comments", 0)},
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
            post.get("url") or f"https://www.reddit.com{post.get('permalink', '')}"
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
            "Name": {"title": [{"text": {"content": f"[Scan] No opportunities — {scanned_at[:10]}"}}]},
            "Status": {"select": {"name": "Skipped"}},
            "Scanned At": {"date": {"start": scanned_at}},
        },
    )
    return page["id"]


def push_mimic_post(profile: dict, subreddit: str, result: dict, client=None) -> str:
    """Push a style mimic post draft to Notion. Returns page ID."""
    if client is None:
        client = get_notion_client()
    db_id = ensure_database(profile["id"], profile, client=client)
    now = datetime.now(timezone.utc).isoformat()
    properties = {
        "Name": {"title": [{"text": {"content": result.get("title", "")[:2000]}}]},
        "Type": {"select": {"name": "Post"}},
        "Status": {"select": {"name": "Draft"}},
        "Subreddit": {"select": {"name": subreddit}},
        "Scanned At": {"date": {"start": now}},
        "Hook Angle": {"rich_text": [{"text": {"content": result.get("why_it_fits", "")[:2000]}}]},
    }
    blocks = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Mimic Post Draft"}}]}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "Title"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": result.get("title", "")}}]}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "Body"}}]}},
    ]
    for chunk in _split_text(result.get("body", "")):
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": chunk}}]}})
    if result.get("why_it_fits"):
        blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "Why It Fits"}}]}})
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": result["why_it_fits"]}}]}})
    page = client.pages.create(
        parent={"database_id": db_id},
        properties=properties,
        children=blocks,
    )
    return page["id"]


def _load_rules_parent_page_id() -> str | None:
    path = _notion_dir() / "rules.config.json"
    if path.exists():
        return json.loads(path.read_text()).get("parent_page_id")
    return os.environ.get("NOTION_RULES_PAGE_ID")


def save_rules_parent_page_id(page_id: str) -> None:
    path = _notion_dir() / "rules.config.json"
    with open(path, "w") as f:
        json.dump({"parent_page_id": page_id}, f)


def _load_rules_page_id(subreddit: str) -> str | None:
    from .profile_store import slugify
    path = _notion_dir() / f"rules_{slugify(subreddit)}.page.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f).get("page_id")


def _save_rules_page_id(subreddit: str, page_id: str) -> None:
    from .profile_store import slugify
    path = _notion_dir() / f"rules_{slugify(subreddit)}.page.json"
    with open(path, "w") as f:
        json.dump({"page_id": page_id}, f)


def _build_rules_blocks(subreddit: str, data: dict) -> list:
    norms = data.get("inferred_norms", {})
    official = data.get("official_rules", [])
    meta = data.get("inference_metadata", {})
    blocks = []

    learned = data.get("norms_learned_at", "")[:10]
    posts = meta.get("posts_analyzed", "?")
    blocks.append({
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": [{"text": {"content": f"更新时间：{learned} · 分析帖子数：{posts}"}}],
            "icon": {"emoji": "🗓️"},
            "color": "gray_background",
        }
    })

    # 整体氛围观察
    vibe = norms.get("整体氛围观察", "")
    if vibe:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "🌐 整体氛围观察"}}]
        }})
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"text": {"content": vibe}}]
        }})

    # 官方规则
    if official:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "📋 官方规则（侧边栏）"}}]
        }})
        for r in official:
            name = r.get("short_name", "")
            desc = r.get("description", "")
            content = f"{name} — {desc[:300]}" if desc else name
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": content}}]
            }})

    # 社群氛围 & 价值观
    tone = norms.get("社群氛围", "")
    values = norms.get("社群价值观", [])
    if tone or values:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "🎯 社群氛围与价值观"}}]
        }})
        if tone:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {
                "rich_text": [{"text": {"content": tone}}]
            }})
        for val in values:
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": val}}]
            }})

    # 会被删除的内容
    removed = norms.get("会被删除的内容", [])
    if removed:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "🚫 会被删除的内容"}}]
        }})
        for item in removed:
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": item}}]
            }})

    # 发帖检查清单
    checklist = norms.get("发帖检查清单", [])
    if checklist:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "✅ 发帖前检查清单"}}]
        }})
        for item in checklist:
            blocks.append({"object": "block", "type": "to_do", "to_do": {
                "rich_text": [{"text": {"content": item}}], "checked": False
            }})

    # 安全发帖角度
    angles = norms.get("安全发帖角度", [])
    if angles:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "💡 安全发帖角度"}}]
        }})
        for item in angles:
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"text": {"content": item}}]
            }})

    # 外链规则
    link_rules = norms.get("外链规则", "")
    if link_rules:
        blocks.append({"object": "block", "type": "heading_2", "heading_2": {
            "rich_text": [{"text": {"content": "🔗 外链规则"}}]
        }})
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {
            "rich_text": [{"text": {"content": link_rules}}]
        }})

    return blocks


def push_rules_profile(subreddit: str, data: dict, client=None) -> str:
    """Push rules profile to Notion. Creates or updates the page. Returns page URL."""
    if client is None:
        client = get_notion_client()

    rules_db_id = _load_rules_parent_page_id()
    if not rules_db_id:
        raise NotionConfigError(
            "Notion rules database not configured. "
            "Run: reddit-toolkit rules notion-setup --page-id <NOTION_DATABASE_OR_PAGE_ID>"
        )

    title = f"r/{subreddit} — Community Rules & Norms"
    blocks = _build_rules_blocks(subreddit, data)
    existing_page_id = _load_rules_page_id(subreddit)
    page_id = None

    if existing_page_id:
        try:
            children = client.blocks.children.list(existing_page_id)
            for block in children.get("results", []):
                client.blocks.delete(block["id"])
            client.blocks.children.append(existing_page_id, children=blocks)
            page_id = existing_page_id
        except Exception:
            page_id = None

    if not page_id:
        # Try as database entry first, fall back to page child
        try:
            page = client.pages.create(
                parent={"type": "database_id", "database_id": rules_db_id},
                properties={"Name": {"title": [{"text": {"content": title}}]}},
                children=blocks,
            )
        except Exception:
            page = client.pages.create(
                parent={"type": "page_id", "page_id": rules_db_id},
                properties={"title": [{"text": {"content": title}}]},
                children=blocks,
            )
        page_id = page["id"]
        _save_rules_page_id(subreddit, page_id)

    return f"https://notion.so/{page_id.replace('-', '')}"


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
