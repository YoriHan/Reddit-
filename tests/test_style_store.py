import json
import os
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        yield tmp_path


def test_save_and_load(tmp_data_dir):
    from reddit_toolkit.style_store import save, load
    data = {"style": {"tone": "casual"}}
    save("python", data)
    loaded = load("python")
    assert loaded["subreddit"] == "python"
    assert loaded["style"]["tone"] == "casual"
    assert "learned_at" in loaded


def test_load_not_found(tmp_data_dir):
    from reddit_toolkit.style_store import load, StyleNotFoundError
    with pytest.raises(StyleNotFoundError, match="reddit-toolkit style learn"):
        load("doesnotexist")


def test_slugify_normalization(tmp_data_dir):
    from reddit_toolkit.style_store import save, load
    save("Python", {"style": {}})
    loaded = load("python")  # lowercase lookup should work
    assert loaded["subreddit"] == "python"


def test_is_stale_old(tmp_data_dir):
    from reddit_toolkit.style_store import is_stale
    from datetime import datetime, timezone, timedelta
    old_dt = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    assert is_stale({"learned_at": old_dt}) is True


def test_is_stale_fresh(tmp_data_dir):
    from reddit_toolkit.style_store import is_stale
    from datetime import datetime, timezone
    fresh_dt = datetime.now(timezone.utc).isoformat()
    assert is_stale({"learned_at": fresh_dt}) is False


def test_list_styles(tmp_data_dir):
    from reddit_toolkit.style_store import save, list_styles
    save("python", {"style": {}})
    save("rust", {"style": {}})
    styles = list_styles()
    names = [s["subreddit"] for s in styles]
    assert "python" in names
    assert "rust" in names
