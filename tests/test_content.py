import pytest
from unittest.mock import MagicMock, patch
from reddit_toolkit.content import (
    get_hot_posts, get_top_posts, get_rising_posts, search_posts, _normalise_post
)

SAMPLE_POST = {
    "title": "Test Post",
    "score": 100,
    "url": "https://example.com",
    "subreddit": "python",
    "author": "user1",
    "num_comments": 42,
    "permalink": "/r/python/comments/abc/test_post/",
    "created_utc": 1700000000.0,
    "selftext": "",
}

LISTING_RESPONSE = {
    "kind": "Listing",
    "data": {
        "children": [
            {"kind": "t3", "data": SAMPLE_POST}
        ]
    }
}


def make_client(response=LISTING_RESPONSE):
    client = MagicMock()
    client.get.return_value = response
    return client


class TestNormalisePost:
    def test_selftext_included(self):
        result = _normalise_post({"selftext": "hello body"})
        assert "selftext" in result
        assert result["selftext"] == "hello body"

    def test_selftext_defaults_to_empty_string(self):
        result = _normalise_post({})
        assert result["selftext"] == ""


class TestGetHotPosts:
    def test_returns_list_of_posts(self):
        result = get_hot_posts("python", limit=5, client=make_client())
        assert isinstance(result, list)
        assert len(result) == 1

    def test_post_has_required_keys(self):
        result = get_hot_posts("python", client=make_client())
        post = result[0]
        for key in ["title", "score", "url", "subreddit", "author", "num_comments", "permalink", "created_utc"]:
            assert key in post, f"Missing key: {key}"

    def test_calls_correct_endpoint(self):
        client = make_client()
        get_hot_posts("python", limit=10, client=client)
        client.get.assert_called_once_with("/r/python/hot.json", {"limit": 10})

    def test_default_subreddit_is_all(self):
        client = make_client()
        get_hot_posts(client=client)
        args = client.get.call_args.args
        assert "/r/all/hot.json" in args[0]


class TestGetTopPosts:
    def test_calls_correct_endpoint_with_timeframe(self):
        client = make_client()
        get_top_posts("python", limit=5, timeframe="month", client=client)
        client.get.assert_called_once_with("/r/python/top.json", {"limit": 5, "t": "month"})

    def test_default_timeframe_is_week(self):
        client = make_client()
        get_top_posts("python", client=client)
        params = client.get.call_args.args[1]
        assert params["t"] == "week"


class TestGetRisingPosts:
    def test_calls_correct_endpoint(self):
        client = make_client()
        get_rising_posts("python", limit=5, client=client)
        client.get.assert_called_once_with("/r/python/rising.json", {"limit": 5})


class TestSearchPosts:
    def test_global_search(self):
        client = make_client()
        search_posts("machine learning", client=client)
        args = client.get.call_args.args
        assert args[0] == "/search.json"
        assert "machine learning" in client.get.call_args.args[1]["q"]

    def test_subreddit_restricted_search(self):
        client = make_client()
        search_posts("asyncio", subreddit="python", client=client)
        args = client.get.call_args.args
        assert args[0] == "/r/python/search.json"
        params = client.get.call_args.args[1]
        assert params.get("restrict_sr") == 1
