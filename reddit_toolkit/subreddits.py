from .reddit_client import RedditClient


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
    if client is None:
        client = RedditClient()
    response = client.get("/subreddits/popular.json", {"limit": limit})
    return _extract_subreddits(response)


def search_subreddits(query: str, limit: int = 10, client=None) -> list:
    if client is None:
        client = RedditClient()
    response = client.get("/subreddits/search.json", {"q": query, "limit": limit})
    return _extract_subreddits(response)


def get_subreddit_info(name: str, client=None) -> dict:
    if client is None:
        client = RedditClient()
    response = client.get(f"/r/{name}/about.json")
    return _normalise_subreddit(response["data"])


def explore_by_topic(topic: str, limit: int = 10, client=None) -> list:
    return search_subreddits(topic, limit=limit, client=client)
