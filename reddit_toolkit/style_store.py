import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .profile_store import slugify


class StyleNotFoundError(Exception):
    pass


def _data_dir() -> Path:
    base = os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")
    return Path(base).expanduser()


def styles_dir() -> Path:
    d = _data_dir() / "styles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(subreddit: str, data: dict) -> None:
    data["subreddit"] = subreddit.lower()
    data["learned_at"] = datetime.now(timezone.utc).isoformat()
    path = styles_dir() / f"{slugify(subreddit)}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load(subreddit: str) -> dict:
    path = styles_dir() / f"{slugify(subreddit)}.json"
    if not path.exists():
        raise StyleNotFoundError(
            f"No style profile for r/{subreddit}. "
            f"Run: reddit-toolkit style learn --subreddit {subreddit}"
        )
    with open(path) as f:
        return json.load(f)


def is_stale(data: dict, max_age_days: int = 7) -> bool:
    learned_at = data.get("learned_at")
    if not learned_at:
        return True
    dt = datetime.fromisoformat(learned_at)
    return datetime.now(timezone.utc) - dt > timedelta(days=max_age_days)


def list_styles() -> list:
    return [json.loads(p.read_text()) for p in sorted(styles_dir().glob("*.json"))]
