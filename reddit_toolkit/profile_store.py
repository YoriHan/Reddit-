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
