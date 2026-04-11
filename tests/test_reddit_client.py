import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.reddit_client import RedditClient, RedditAPIError


def make_mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status.side_effect = (
        None if status_code < 400
        else Exception(f"HTTP {status_code}")
    )
    return mock


class TestRedditClientGet:
    def test_success_returns_json(self):
        expected = {"kind": "Listing", "data": {"children": []}}
        with patch("requests.get", return_value=make_mock_response(expected)) as mock_get:
            client = RedditClient()
            result = client.get("/r/python/hot.json", {"limit": 5})
        assert result == expected
        call_args = mock_get.call_args
        assert "RedditToolkit" in call_args.kwargs["headers"]["User-Agent"]
        assert call_args.kwargs["params"]["limit"] == 5

    def test_http_error_raises_reddit_api_error(self):
        with patch("requests.get", return_value=make_mock_response({}, 404)):
            client = RedditClient()
            with pytest.raises(RedditAPIError):
                client.get("/r/doesnotexist/hot.json")

    def test_correct_base_url(self):
        with patch("requests.get", return_value=make_mock_response({})) as mock_get:
            client = RedditClient()
            client.get("/r/python/hot.json")
        url = mock_get.call_args.args[0]
        assert url == "https://www.reddit.com/r/python/hot.json"

    def test_rate_limit_sleep_called(self):
        with patch("requests.get", return_value=make_mock_response({})):
            with patch("time.sleep") as mock_sleep:
                client = RedditClient()
                client.get("/r/python/hot.json")
        mock_sleep.assert_called_once_with(1)
