import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _tracker_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    d = Path(base).expanduser() / "tracker"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_tracked(product_id: str) -> dict:
    path = _tracker_dir() / f"{product_id}.json"
    if not path.exists():
        return {"subreddits": [], "last_discovery": None}
    return json.loads(path.read_text())


def save_tracked(product_id: str, data: dict) -> None:
    path = _tracker_dir() / f"{product_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def add_subreddits(product_id: str, candidates: list) -> int:
    """Merge new candidates into the tracked list. Returns count of newly added."""
    data = load_tracked(product_id)
    existing = {s["name"].lower() for s in data["subreddits"]}
    added = 0
    for s in candidates:
        if s["name"].lower() not in existing:
            data["subreddits"].append({
                "name": s["name"],
                "why": s.get("why", ""),
                "added_at": datetime.now(timezone.utc).isoformat(),
            })
            existing.add(s["name"].lower())
            added += 1
    data["last_discovery"] = datetime.now(timezone.utc).isoformat()
    save_tracked(product_id, data)
    return added


def list_tracked(product_id: str) -> list:
    return load_tracked(product_id).get("subreddits", [])
