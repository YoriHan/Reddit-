from .reddit_client import RedditClient


def _client(client) -> RedditClient:
    return client if client is not None else RedditClient()


def _normalise_post(data: dict) -> dict:
    return {
        "title": data.get("title", ""),
        "score": data.get("score", 0),
        "url": data.get("url", ""),
        "subreddit": data.get("subreddit", ""),
        "author": data.get("author", ""),
        "num_comments": data.get("num_comments", 0),
        "permalink": data.get("permalink", ""),
        "created_utc": data.get("created_utc", 0.0),
    }


def _extract_posts(response: dict) -> list:
    return [
        _normalise_post(child["data"])
        for child in response.get("data", {}).get("children", [])
        if child.get("kind") == "t3"
    ]


def get_hot_posts(subreddit: str = "all", limit: int = 10, client=None) -> list:
    response = _client(client).get(f"/r/{subreddit}/hot.json", {"limit": limit})
    return _extract_posts(response)


def get_top_posts(subreddit: str = "all", limit: int = 10, timeframe: str = "week", client=None) -> list:
    response = _client(client).get(f"/r/{subreddit}/top.json", {"limit": limit, "t": timeframe})
    return _extract_posts(response)


def get_rising_posts(subreddit: str = "all", limit: int = 10, client=None) -> list:
    response = _client(client).get(f"/r/{subreddit}/rising.json", {"limit": limit})
    return _extract_posts(response)


def search_posts(query: str, subreddit: str = None, limit: int = 10, sort: str = "relevance", client=None) -> list:
    if subreddit:
        path = f"/r/{subreddit}/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "restrict_sr": 1}
    else:
        path = "/search.json"
        params = {"q": query, "limit": limit, "sort": sort}
    response = _client(client).get(path, params)
    return _extract_posts(response)
