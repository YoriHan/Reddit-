import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .profile_store import slugify


class RulesNotFoundError(Exception):
    pass


def _data_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    return Path(base).expanduser()


def rules_dir() -> Path:
    d = _data_dir() / "rules"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(subreddit: str, data: dict) -> None:
    data["subreddit"] = subreddit.lower().strip().lstrip("r/")
    path = rules_dir() / f"{slugify(subreddit)}.rules.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load(subreddit: str) -> dict:
    path = rules_dir() / f"{slugify(subreddit)}.rules.json"
    if not path.exists():
        raise RulesNotFoundError(
            f"No rules profile for r/{subreddit}. "
            f"Run: reddit-toolkit rules learn --subreddit {subreddit}"
        )
    with open(path) as f:
        return json.load(f)


def is_stale_norms(data: dict, max_age_days: int = 7) -> bool:
    ts = data.get("norms_learned_at")
    if not ts:
        return True
    dt = datetime.fromisoformat(ts)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)


def is_stale_rules(data: dict, max_age_days: int = 30) -> bool:
    ts = data.get("rules_fetched_at")
    if not ts:
        return True
    dt = datetime.fromisoformat(ts)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)


def list_rules() -> list:
    return [json.loads(p.read_text()) for p in sorted(rules_dir().glob("*.rules.json"))]
