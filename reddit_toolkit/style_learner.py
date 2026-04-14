import warnings

from .reddit_client import RedditClient
from .content import _extract_posts


def fetch_subreddit_corpus(
    subreddit: str,
    pages: int = 10,
    per_page: int = 25,
    client=None,
) -> list:
    """Fetch posts from a subreddit across multiple pages.

    Fetches top-all posts (paginated) then hot posts for recency signal.
    Deduplicates by permalink. Respects RedditClient's built-in 1s rate limit.
    If client is a PRAWClient, also fetches top comments for the first 5 posts.

    Returns:
        List of normalised post dicts (same schema as content._normalise_post)
    """
    c = client or RedditClient()
    all_posts = []
    seen_permalinks = set()

    # Phase 1: top-all (most culturally representative)
    after = None
    for page_num in range(1, pages + 1):
        print(f"  Fetching page {page_num}/{pages}...", flush=True)
        params = {"limit": per_page, "t": "all"}
        if after:
            params["after"] = after
        response = c.get(f"/r/{subreddit}/top.json", params)
        batch = _extract_posts(response)
        if not batch:
            break
        for post in batch:
            if post["permalink"] not in seen_permalinks:
                seen_permalinks.add(post["permalink"])
                all_posts.append(post)
        after = response.get("data", {}).get("after")
        if not after:
            break

    # Phase 2: hot posts for recency signal
    response = c.get(f"/r/{subreddit}/hot.json", {"limit": 25})
    for post in _extract_posts(response):
        if post["permalink"] not in seen_permalinks:
            seen_permalinks.add(post["permalink"])
            all_posts.append(post)

    # Phase 3: optional comment enrichment (PRAWClient only)
    from .praw_client import PRAWClient  # noqa: PLC0415 — lazy to avoid circular at module top
    if isinstance(c, PRAWClient):
        for post in all_posts[:5]:
            try:
                comments = c.fetch_comments_for_post(post["permalink"], limit=10)
                for body in comments:
                    if body.strip():
                        key = f"__comment__{body[:50]}"
                        if key not in seen_permalinks:
                            seen_permalinks.add(key)
                            all_posts.append({**post, "title": body, "selftext": body,
                                              "permalink": key})
            except Exception as e:
                warnings.warn(f"Comment fetch failed for {post.get('permalink')}: {e}")

    return all_posts
