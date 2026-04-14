import os
from unittest.mock import MagicMock, patch
import pytest


def make_mock_submission(title="Post", score=100, author="user"):
    sub = MagicMock()
    sub.title = title
    sub.score = score
    sub.url = "https://x.com"
    sub.subreddit = MagicMock()
    sub.subreddit.__str__ = lambda self: "python"
    sub.author = MagicMock()
    sub.author.__str__ = lambda self: author
    sub.num_comments = 5
    sub.permalink = "/r/python/comments/abc/test/"
    sub.created_utc = 1700000000.0
    sub.selftext = ""
    return sub


class TestPRAWClient:
    def test_get_returns_expected_schema(self):
        mock_submission = make_mock_submission()
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.top.return_value = [mock_submission]
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import PRAWClient
                client = PRAWClient()
                result = client.get("/r/python/top.json", {"t": "all", "limit": 10})
        assert "data" in result
        assert "children" in result["data"]
        assert result["data"]["children"][0]["kind"] == "t3"
        data = result["data"]["children"][0]["data"]
        assert data["title"] == "Post"
        assert data["author"] == "user"

    def test_deleted_author_serialised_as_string(self):
        mock_submission = make_mock_submission()
        mock_submission.author = None
        mock_reddit = MagicMock()
        mock_reddit.subreddit.return_value.top.return_value = [mock_submission]
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import PRAWClient
                client = PRAWClient()
                result = client.get("/r/python/top.json", {"t": "all", "limit": 5})
        assert result["data"]["children"][0]["data"]["author"] == "[deleted]"

    def test_make_praw_client_if_configured_returns_none_when_no_env(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")}
        with patch.dict(os.environ, env, clear=True):
            from reddit_toolkit.praw_client import make_praw_client_if_configured
            result = make_praw_client_if_configured()
        assert result is None

    def test_make_praw_client_if_configured_returns_client_when_env_set(self):
        mock_reddit = MagicMock()
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"}):
            with patch("reddit_toolkit.praw_client.praw.Reddit", return_value=mock_reddit):
                from reddit_toolkit.praw_client import make_praw_client_if_configured, PRAWClient
                result = make_praw_client_if_configured()
        assert isinstance(result, PRAWClient)
