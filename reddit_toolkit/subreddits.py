from .reddit_client import RedditClient


def _client(client) -> RedditClient:
    return client if client is not None else RedditClient()


def _normalise_subreddit(data: dict) -> dict:
    return {
        "display_name": data.get("display_name", ""),
        "title": data.get("title", ""),
        "subscribers": data.get("subscribers", 0),
        "active_user_count": data.get("active_user_count", 0),
        "subreddit_type": data.get("subreddit_type", "public"),
        "over18": data.get("over18", False),
        "allow_images": data.get("allow_images", True),
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


def validate_subreddit_for_promotion(name: str, min_subscribers: int = 5000, client=None) -> dict:
    """Fetch real subreddit metadata and decide if it's viable for promotion.

    Returns a dict with:
      - "ok": bool  — passes minimum bar
      - "subscribers": int
      - "active_users": int
      - "reason": str  — why it was rejected (empty if ok)
      - all other normalised fields
    """
    try:
        c = _client(client)
        response = c.get(f"/r/{name}/about.json")
        data = response.get("data")
        if not data:
            return {"ok": False, "subscribers": 0, "active_users": 0, "reason": "subreddit not found"}

        info = _normalise_subreddit(data)
        sub_type = info.get("subreddit_type", "public")
        subscribers = info.get("subscribers", 0)
        active = info.get("active_user_count", 0)

        if sub_type not in ("public",):
            return {**info, "ok": False, "active_users": active, "reason": f"type={sub_type} (not public)"}
        if subscribers < min_subscribers:
            return {**info, "ok": False, "active_users": active, "reason": f"only {subscribers:,} subscribers (min {min_subscribers:,})"}

        return {**info, "ok": True, "active_users": active, "reason": ""}

    except Exception as e:
        # Network errors etc. — give benefit of the doubt
        return {"ok": True, "subscribers": 0, "active_users": 0, "reason": f"validation skipped: {e}"}
