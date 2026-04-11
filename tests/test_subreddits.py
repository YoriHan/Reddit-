import pytest
from unittest.mock import MagicMock
from reddit_toolkit.subreddits import (
    get_popular_subreddits, search_subreddits, get_subreddit_info, explore_by_topic
)

SAMPLE_SUB = {
    "display_name": "python",
    "title": "Python",
    "subscribers": 1468454,
    "public_description": "The largest Python community for Reddit.",
    "url": "/r/python/",
}

SUBREDDIT_LISTING = {
    "kind": "Listing",
    "data": {"children": [{"kind": "t5", "data": SAMPLE_SUB}]}
}

ABOUT_RESPONSE = {
    "kind": "t5",
    "data": SAMPLE_SUB
}


def make_client(response):
    client = MagicMock()
    client.get.return_value = response
    return client


class TestGetPopularSubreddits:
    def test_calls_correct_endpoint(self):
        client = make_client(SUBREDDIT_LISTING)
        get_popular_subreddits(limit=5, client=client)
        client.get.assert_called_once_with("/subreddits/popular.json", {"limit": 5})

    def test_returns_normalised_list(self):
        result = get_popular_subreddits(client=make_client(SUBREDDIT_LISTING))
        assert isinstance(result, list)
        assert result[0]["display_name"] == "python"
        assert result[0]["subscribers"] == 1468454

    def test_result_has_required_keys(self):
        result = get_popular_subreddits(client=make_client(SUBREDDIT_LISTING))
        for key in ["display_name", "title", "subscribers", "description", "url"]:
            assert key in result[0], f"Missing key: {key}"


class TestSearchSubreddits:
    def test_calls_search_endpoint(self):
        client = make_client(SUBREDDIT_LISTING)
        search_subreddits("programming", limit=10, client=client)
        client.get.assert_called_once_with("/subreddits/search.json", {"q": "programming", "limit": 10})


class TestGetSubredditInfo:
    def test_calls_about_endpoint(self):
        client = make_client(ABOUT_RESPONSE)
        get_subreddit_info("python", client=client)
        client.get.assert_called_once_with("/r/python/about.json")

    def test_returns_single_subreddit_dict(self):
        result = get_subreddit_info("python", client=make_client(ABOUT_RESPONSE))
        assert result["display_name"] == "python"
        assert "subscribers" in result

    def test_missing_data_key_raises_key_error(self):
        # Simulates a banned/quarantined subreddit returning an unexpected shape.
        bad_response = {"kind": "t5"}  # no "data" key
        with pytest.raises(KeyError, match="data"):
            get_subreddit_info("banned_sub", client=make_client(bad_response))


class TestExploreByTopic:
    def test_is_alias_for_search(self):
        client = make_client(SUBREDDIT_LISTING)
        result = explore_by_topic("machine learning", limit=5, client=client)
        client.get.assert_called_once_with("/subreddits/search.json", {"q": "machine learning", "limit": 5})
        assert isinstance(result, list)
