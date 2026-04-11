import time
import requests


class RedditAPIError(Exception):
    """Raised when the Reddit API returns an error response."""
    pass


class RedditClient:
    BASE_URL = "https://www.reddit.com"
    USER_AGENT = "RedditToolkit/0.1.0 (by /u/toolkit_user)"

    def get(self, path: str, params: dict = None) -> dict:
        """Make a GET request to the Reddit JSON API.

        Args:
            path: URL path starting with '/', e.g. '/r/python/hot.json'
            params: Optional dict of query parameters

        Returns:
            Parsed JSON response as a dict

        Raises:
            RedditAPIError: on HTTP error responses
        """
        url = self.BASE_URL + path
        headers = {"User-Agent": self.USER_AGENT}
        response = requests.get(url, params=params or {}, headers=headers)
        time.sleep(1)
        try:
            response.raise_for_status()
        except Exception as e:
            raise RedditAPIError(f"Reddit API error: {e}") from e
        return response.json()
