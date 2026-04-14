import pytest
from unittest.mock import MagicMock
from reddit_toolkit.style_learner import fetch_subreddit_corpus

SAMPLE_POST = {
    "title": "Test post", "score": 100, "url": "https://x.com",
    "subreddit": "python", "author": "u1", "num_comments": 5,
    "permalink": "/r/python/comments/a/test/", "created_utc": 1700000000.0, "selftext": "",
}

def make_listing(posts, after=None):
    return {
        "data": {
            "after": after,
            "children": [{"kind": "t3", "data": p} for p in posts],
        }
    }


def make_client(responses):
    """responses: list of dicts returned in order."""
    client = MagicMock()
    client.get.side_effect = responses
    return client


def test_fetches_single_page_when_after_is_null():
    post = {**SAMPLE_POST}
    client = make_client([
        make_listing([post], after=None),  # top page 1
        make_listing([]),                  # hot
    ])
    result = fetch_subreddit_corpus("python", pages=10, per_page=25, client=client)
    assert len(result) == 1
    # Only called twice: 1 top page (after=None stops it) + 1 hot
    assert client.get.call_count == 2


def test_paginates_up_to_pages_limit():
    post1 = {**SAMPLE_POST, "permalink": "/a/"}
    post2 = {**SAMPLE_POST, "permalink": "/b/"}
    client = make_client([
        make_listing([post1], after="t3_abc"),  # top page 1
        make_listing([post2], after=None),       # top page 2 (after=None stops)
        make_listing([]),                         # hot
    ])
    result = fetch_subreddit_corpus("python", pages=5, per_page=25, client=client)
    assert len(result) == 2


def test_deduplicates_across_phases():
    post = {**SAMPLE_POST}
    client = make_client([
        make_listing([post], after=None),  # top
        make_listing([post]),              # hot — same permalink, should dedup
    ])
    result = fetch_subreddit_corpus("python", pages=1, client=client)
    assert len(result) == 1


def test_passes_after_cursor_to_second_page():
    post1 = {**SAMPLE_POST, "permalink": "/a/"}
    post2 = {**SAMPLE_POST, "permalink": "/b/"}
    client = make_client([
        make_listing([post1], after="t3_cursor123"),
        make_listing([post2], after=None),
        make_listing([]),
    ])
    fetch_subreddit_corpus("python", pages=5, per_page=10, client=client)
    second_call_params = client.get.call_args_list[1].args[1]
    assert second_call_params["after"] == "t3_cursor123"


def test_stops_early_if_empty_batch():
    client = make_client([
        make_listing([]),  # empty on first page → break immediately
        make_listing([]),  # hot
    ])
    result = fetch_subreddit_corpus("python", pages=10, client=client)
    assert result == []
