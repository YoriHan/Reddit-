from .reddit_client import RedditClient


def _client(client) -> RedditClient:
    return client if client is not None else RedditClient()


def _normalise_subreddit(data: dict) -> dict:
    return {
        "display_name": data.get("display_name", ""),
        "title": data.get("title", ""),
        "subscribers": data.get("subscribers", 0),
        "description": data.get("public_description", ""),
        "url": data.get("url", ""),
    }


def _extract_subreddits(response: dict) -> list:
    return [
        _normalise_subreddit(child["data"])
        for child in response.get("data", {}).get("children", [])
        if child.get("kind") == "t5"
    ]


def get_popular_subreddits(limit: int = 20, client=None) -> list:
    response = _client(client).get("/subreddits/popular.json", {"limit": limit})
    return _extract_subreddits(response)


def search_subreddits(query: str, limit: int = 10, client=None) -> list:
    response = _client(client).get("/subreddits/search.json", {"q": query, "limit": limit})
    return _extract_subreddits(response)


def get_subreddit_info(name: str, client=None) -> dict:
    response = _client(client).get(f"/r/{name}/about.json")
    data = response.get("data")
    if data is None:
        raise KeyError(f"Unexpected API response for subreddit '{name}': 'data' key missing.")
    return _normalise_subreddit(data)


def explore_by_topic(topic: str, limit: int = 10, client=None) -> list:
    return search_subreddits(topic, limit=limit, client=client)
