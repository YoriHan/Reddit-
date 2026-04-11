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
    """NotionConfigError is raised when token is missing (or notion-client not installed)."""
    env = {k: v for k, v in os.environ.items() if k != "NOTION_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(NotionConfigError):
            get_notion_client()
