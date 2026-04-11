# tests/test_scanner.py
import json
import os
import pytest
from unittest.mock import patch, MagicMock, call
from reddit_toolkit.scanner import run_scan, _fetch_posts, _load_seen, _save_seen, ScanResult


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


def test_seen_empty_on_first_run(tmp_path):
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path)}):
        seen = _load_seen("nonexistent-product")
    assert seen == set()


def test_run_scan_dry_run_no_notion(tmp_path):
    """Dry run should score posts but not push to Notion."""
    mock_reddit_client = MagicMock()
    mock_reddit_client.get.return_value = {
        "data": {"children": [{"kind": "t3", "data": {
            "title": "Test post", "score": 100, "url": "https://example.com",
            "subreddit": "python", "author": "user", "num_comments": 10,
            "permalink": "/r/python/comments/abc", "created_utc": 0.0, "selftext": "",
        }}]}
    }
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner.score_post_for_product",
                   return_value={"score": 9, "hook_angle": "relevant", "reasoning": "matches"}):
            with patch("reddit_toolkit.scanner.generate_opportunity_draft",
                       return_value={"title": "Draft", "body": "Body"}):
                with patch("time.sleep"):
                    result = run_scan(SAMPLE_PROFILE, dry_run=True, reddit_client=mock_reddit_client)
    assert isinstance(result, ScanResult)
    assert result.product_id == "test-app"


def test_threshold_filtering(tmp_path):
    """Posts below threshold should not become opportunities."""
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner._fetch_posts", return_value=[SAMPLE_POST]):
            with patch("reddit_toolkit.scanner.score_post_for_product",
                       return_value={"score": 3, "hook_angle": "", "reasoning": ""}):
                with patch("time.sleep"):
                    result = run_scan(SAMPLE_PROFILE, dry_run=True)
    assert len(result.opportunities) == 0


def test_top_n_limits_opportunities(tmp_path):
    """Only top_n opportunities should be returned."""
    posts = [
        {**SAMPLE_POST, "permalink": f"/r/python/comments/{i}", "title": f"Post {i}"}
        for i in range(5)
    ]
    scores = [{"score": 8 + i % 2, "hook_angle": f"hook{i}", "reasoning": "r"} for i in range(5)]

    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner._fetch_posts", return_value=posts):
            with patch("reddit_toolkit.scanner.score_post_for_product", side_effect=scores):
                with patch("reddit_toolkit.scanner.generate_opportunity_draft",
                           return_value={"title": "T", "body": "B"}):
                    with patch("time.sleep"):
                        result = run_scan(SAMPLE_PROFILE, dry_run=True, top_n=2)
    assert len(result.opportunities) <= 2


def test_notion_push_fn_called(tmp_path):
    """notion_push_fn should be called once per opportunity."""
    push_calls = []
    with patch.dict(os.environ, {"REDDIT_TOOLKIT_DATA_DIR": str(tmp_path), "ANTHROPIC_API_KEY": "k"}):
        with patch("reddit_toolkit.scanner._fetch_posts", return_value=[SAMPLE_POST]):
            with patch("reddit_toolkit.scanner.score_post_for_product",
                       return_value={"score": 9, "hook_angle": "h", "reasoning": "r"}):
                with patch("reddit_toolkit.scanner.generate_opportunity_draft",
                           return_value={"title": "T", "body": "B"}):
                    with patch("time.sleep"):
                        run_scan(SAMPLE_PROFILE, notion_push_fn=push_calls.append)
    assert len(push_calls) == 1
    assert push_calls[0] is not None
