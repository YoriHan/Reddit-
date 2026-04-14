"""Optional PRAW-based Reddit client for comment enrichment.

Activated when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars are set.
Provides the same .get() interface as RedditClient plus .fetch_comments_for_post().
"""
import os
import praw


def _make_reddit():
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "reddit-toolkit/1.0"),
    )


def _serialise_submission(sub):
    return {
        "title": sub.title,
        "score": sub.score,
        "url": sub.url,
        "subreddit": str(sub.subreddit),
        "author": str(sub.author) if sub.author else "[deleted]",
        "num_comments": sub.num_comments,
        "permalink": sub.permalink,
        "created_utc": float(sub.created_utc),
        "selftext": sub.selftext,
    }


class PRAWClient:
    """PRAW-backed client with same .get() interface as RedditClient."""

    def __init__(self):
        self._reddit = _make_reddit()

    def get(self, path: str, params: dict = None) -> dict:
        params = params or {}
        parts = path.strip("/").split("/")
        # Expected paths: r/{sub}/top.json or r/{sub}/hot.json
        if len(parts) < 3 or parts[0] != "r":
            return {"data": {"after": None, "children": []}}
        subreddit_name = parts[1]
        sort = parts[2].replace(".json", "")
        limit = int(params.get("limit", 25))
        sub = self._reddit.subreddit(subreddit_name)
        if sort == "top":
            time_filter = params.get("t", "all")
            listings = list(sub.top(time_filter=time_filter, limit=limit))
        else:
            listings = list(sub.hot(limit=limit))
        children = [{"kind": "t3", "data": _serialise_submission(s)} for s in listings]
        return {"data": {"after": None, "children": children}}

    def fetch_comments_for_post(self, permalink: str, limit: int = 20) -> list:
        """Return top-level comment bodies for a post."""
        submission = self._reddit.submission(url=f"https://www.reddit.com{permalink}")
        submission.comments.replace_more(limit=0)
        comments = []
        for comment in submission.comments[:limit]:
            if hasattr(comment, "body") and comment.body not in ("[deleted]", "[removed]"):
                comments.append(comment.body)
        return comments


def make_praw_client_if_configured():
    """Return PRAWClient if env vars set, else None."""
    if os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"):
        return PRAWClient()
    return None
