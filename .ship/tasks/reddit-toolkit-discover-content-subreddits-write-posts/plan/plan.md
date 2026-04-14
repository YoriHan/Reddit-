# Plan: Reddit Toolkit — Discover Content, Subreddits, Write Posts

**HEAD SHA:** 4c7ea28
**Branch:** ship/reddit-toolkit-discover-content-subreddits-write-posts
**Spec:** `.ship/tasks/reddit-toolkit-discover-content-subreddits-write-posts/plan/spec.md`

---

## Overview

Build a Python CLI tool at `/Users/yorihan/Reddit小工具` with:
- `reddit_toolkit/` package (6 modules)
- `tests/` suite (4 test files)
- `pyproject.toml` with entry point `reddit-toolkit`
- `requirements.txt`

All tasks are TDD: write tests first, then implementation.

---

## Task 1 — Project Scaffold

**Goal:** Create directory structure and package configuration.

- [ ] Create `/Users/yorihan/Reddit小工具/reddit_toolkit/__init__.py` (empty, establishes package)
- [ ] Create `/Users/yorihan/Reddit小工具/tests/__init__.py` (empty)
- [ ] Create `/Users/yorihan/Reddit小工具/requirements.txt` with exact content:
  ```
  requests>=2.33.1
  anthropic>=0.94.0
  ```
- [ ] Create `/Users/yorihan/Reddit小工具/pyproject.toml` with content:
  ```toml
  [build-system]
  requires = ["setuptools>=68"]
  build-backend = "setuptools.backends.legacy:build"

  [project]
  name = "reddit-toolkit"
  version = "0.1.0"
  description = "CLI toolkit to discover Reddit content and write Reddit posts"
  requires-python = ">=3.10"
  dependencies = [
      "requests>=2.33.1",
      "anthropic>=0.94.0",
  ]

  [project.scripts]
  reddit-toolkit = "reddit_toolkit.cli:main"

  [tool.setuptools.packages.find]
  where = ["."]
  include = ["reddit_toolkit*"]
  ```
- [ ] Install editable: `pip3 install -e /Users/yorihan/Reddit小工具 --break-system-packages --quiet`
- [ ] Verify: `reddit-toolkit --help` prints usage without error

---

## Task 2 — RedditClient (TDD)

**Goal:** Implement `reddit_client.py` with HTTP wrapper.

### 2a. Write tests first

Create `/Users/yorihan/Reddit小工具/tests/test_reddit_client.py`:

```python
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
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_reddit_client.py -v` — expect 4 failures (module missing)

### 2b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/reddit_client.py`:

```python
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
        try:
            response = requests.get(url, params=params or {}, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RedditAPIError(f"Reddit API error: {e}") from e
        finally:
            time.sleep(1)
        return response.json()
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_reddit_client.py -v` — expect 4 passes

---

## Task 3 — Content Discovery (TDD)

**Goal:** Implement `content.py` with 4 discovery functions.

### 3a. Write tests first

Create `/Users/yorihan/Reddit小工具/tests/test_content.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from reddit_toolkit.content import (
    get_hot_posts, get_top_posts, get_rising_posts, search_posts
)

SAMPLE_POST = {
    "title": "Test Post",
    "score": 100,
    "url": "https://example.com",
    "subreddit": "python",
    "author": "user1",
    "num_comments": 42,
    "permalink": "/r/python/comments/abc/test_post/",
    "created_utc": 1700000000.0,
    "selftext": "",
}

LISTING_RESPONSE = {
    "kind": "Listing",
    "data": {
        "children": [
            {"kind": "t3", "data": SAMPLE_POST}
        ]
    }
}


def make_client(response=LISTING_RESPONSE):
    client = MagicMock()
    client.get.return_value = response
    return client


class TestGetHotPosts:
    def test_returns_list_of_posts(self):
        result = get_hot_posts("python", limit=5, client=make_client())
        assert isinstance(result, list)
        assert len(result) == 1

    def test_post_has_required_keys(self):
        result = get_hot_posts("python", client=make_client())
        post = result[0]
        for key in ["title", "score", "url", "subreddit", "author", "num_comments", "permalink", "created_utc"]:
            assert key in post, f"Missing key: {key}"

    def test_calls_correct_endpoint(self):
        client = make_client()
        get_hot_posts("python", limit=10, client=client)
        client.get.assert_called_once_with("/r/python/hot.json", {"limit": 10})

    def test_default_subreddit_is_all(self):
        client = make_client()
        get_hot_posts(client=client)
        args = client.get.call_args.args
        assert "/r/all/hot.json" in args[0]


class TestGetTopPosts:
    def test_calls_correct_endpoint_with_timeframe(self):
        client = make_client()
        get_top_posts("python", limit=5, timeframe="month", client=client)
        client.get.assert_called_once_with("/r/python/top.json", {"limit": 5, "t": "month"})

    def test_default_timeframe_is_week(self):
        client = make_client()
        get_top_posts("python", client=client)
        params = client.get.call_args.args[1]
        assert params["t"] == "week"


class TestGetRisingPosts:
    def test_calls_correct_endpoint(self):
        client = make_client()
        get_rising_posts("python", limit=5, client=client)
        client.get.assert_called_once_with("/r/python/rising.json", {"limit": 5})


class TestSearchPosts:
    def test_global_search(self):
        client = make_client()
        search_posts("machine learning", client=client)
        args = client.get.call_args.args
        assert args[0] == "/search.json"
        assert "machine learning" in client.get.call_args.args[1]["q"]

    def test_subreddit_restricted_search(self):
        client = make_client()
        search_posts("asyncio", subreddit="python", client=client)
        args = client.get.call_args.args
        assert args[0] == "/r/python/search.json"
        params = client.get.call_args.args[1]
        assert params.get("restrict_sr") == 1
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_content.py -v` — expect failures (module missing)

### 3b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/content.py`:

```python
from .reddit_client import RedditClient


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
    if client is None:
        client = RedditClient()
    response = client.get(f"/r/{subreddit}/hot.json", {"limit": limit})
    return _extract_posts(response)


def get_top_posts(subreddit: str = "all", limit: int = 10, timeframe: str = "week", client=None) -> list:
    if client is None:
        client = RedditClient()
    response = client.get(f"/r/{subreddit}/top.json", {"limit": limit, "t": timeframe})
    return _extract_posts(response)


def get_rising_posts(subreddit: str = "all", limit: int = 10, client=None) -> list:
    if client is None:
        client = RedditClient()
    response = client.get(f"/r/{subreddit}/rising.json", {"limit": limit})
    return _extract_posts(response)


def search_posts(query: str, subreddit: str = None, limit: int = 10, sort: str = "relevance", client=None) -> list:
    if client is None:
        client = RedditClient()
    if subreddit:
        path = f"/r/{subreddit}/search.json"
        params = {"q": query, "limit": limit, "sort": sort, "restrict_sr": 1}
    else:
        path = "/search.json"
        params = {"q": query, "limit": limit, "sort": sort}
    response = client.get(path, params)
    return _extract_posts(response)
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_content.py -v` — expect all passes

---

## Task 4 — Subreddit Discovery (TDD)

**Goal:** Implement `subreddits.py` with 4 discovery functions.

### 4a. Write tests first

Create `/Users/yorihan/Reddit小工具/tests/test_subreddits.py`:

```python
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


class TestExploreByTopic:
    def test_is_alias_for_search(self):
        client = make_client(SUBREDDIT_LISTING)
        result = explore_by_topic("machine learning", limit=5, client=client)
        client.get.assert_called_once_with("/subreddits/search.json", {"q": "machine learning", "limit": 5})
        assert isinstance(result, list)
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_subreddits.py -v` — expect failures

### 4b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/subreddits.py`:

```python
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
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_subreddits.py -v` — expect all passes

---

## Task 5 — Writing Assistant (TDD)

**Goal:** Implement `writer.py` using Claude API.

### 5a. Write tests first

Create `/Users/yorihan/Reddit小工具/tests/test_writer.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.writer import (
    generate_post_title, write_post_body, generate_comment, WriterConfigError
)


def make_anthropic_mock(text_response: str):
    """Create a mock that mimics anthropic.Anthropic().messages.create() return value."""
    mock_content = MagicMock()
    mock_content.text = text_response
    mock_message = MagicMock()
    mock_message.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    return mock_client


class TestWriterConfigError:
    def test_raises_if_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ANTHROPIC_API_KEY is not set
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with pytest.raises(WriterConfigError, match="ANTHROPIC_API_KEY"):
                generate_post_title("python", "asyncio tips")


class TestGeneratePostTitle:
    def test_returns_list_of_strings(self):
        mock_client = make_anthropic_mock("1. First title\n2. Second title\n3. Third title")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = generate_post_title("python", "asyncio tips")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(t, str) for t in result)

    def test_calls_messages_create_with_model(self):
        mock_client = make_anthropic_mock("1. Title one\n2. Title two")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "REDDIT_TOOLKIT_MODEL": "claude-opus-4-5"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                generate_post_title("python", "asyncio")
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-5"

    def test_subreddit_in_prompt(self):
        mock_client = make_anthropic_mock("1. A title")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                generate_post_title("learnpython", "decorators")
        messages = mock_client.messages.create.call_args.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "learnpython" in prompt_text


class TestWritePostBody:
    def test_returns_string(self):
        mock_client = make_anthropic_mock("This is the post body content.")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = write_post_body("python", "My asyncio post title")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateComment:
    def test_returns_string(self):
        mock_client = make_anthropic_mock("Great post! Here is my comment.")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = generate_comment("Some post title", "Some post body")
        assert isinstance(result, str)

    def test_tone_included_in_prompt(self):
        mock_client = make_anthropic_mock("funny comment here")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                generate_comment("Title", tone="funny")
        messages = mock_client.messages.create.call_args.kwargs["messages"]
        prompt_text = " ".join(m["content"] for m in messages)
        assert "funny" in prompt_text.lower()
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_writer.py -v` — expect failures

### 5b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/writer.py`:

```python
import os
import anthropic


class WriterConfigError(Exception):
    """Raised when writer configuration is missing (e.g. no API key)."""
    pass


def _make_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise WriterConfigError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it with: export ANTHROPIC_API_KEY=your_key_here"
        )
    return anthropic.Anthropic(api_key=api_key)


def _get_model() -> str:
    return os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5")


def _call_claude(client, system_prompt: str, user_prompt: str) -> str:
    response = client.messages.create(
        model=_get_model(),
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def generate_post_title(subreddit: str, topic: str, context: str = "") -> list:
    """Generate 3-5 Reddit post title suggestions.

    Returns:
        List of title strings
    """
    client = _make_client()
    system = (
        f"You are a Reddit expert who writes engaging post titles for r/{subreddit}. "
        "Write titles that are clear, compelling, and appropriate for the subreddit's culture. "
        "Return a numbered list of 3-5 title suggestions, one per line. "
        "Do not include any other text besides the numbered list."
    )
    user = f"Generate post titles about: {topic}"
    if context:
        user += f"\n\nAdditional context: {context}"
    raw = _call_claude(client, system, user)
    lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
    titles = []
    for line in lines:
        # Strip leading numbering like "1." or "1)"
        if line and line[0].isdigit():
            parts = line.split(".", 1) if "." in line else line.split(")", 1)
            if len(parts) == 2:
                titles.append(parts[1].strip())
            else:
                titles.append(line)
        else:
            titles.append(line)
    return titles if titles else [raw.strip()]


def write_post_body(subreddit: str, title: str, context: str = "") -> str:
    """Write a Reddit post body in markdown format.

    Returns:
        Markdown string for the post body
    """
    client = _make_client()
    system = (
        f"You are a Reddit expert writing posts for r/{subreddit}. "
        "Write engaging, well-structured post bodies in markdown. "
        "Match the tone and style appropriate for the subreddit. "
        "Be concise but thorough."
    )
    user = f"Write a post body for this title: {title}"
    if context:
        user += f"\n\nAdditional context: {context}"
    return _call_claude(client, system, user)


def generate_comment(post_title: str, post_body: str = "", post_context: str = "", tone: str = "neutral") -> str:
    """Generate a helpful Reddit comment.

    Args:
        post_title: The title of the post being commented on
        post_body: Optional post body text
        post_context: Optional additional context
        tone: One of neutral, funny, supportive, critical

    Returns:
        Comment text string
    """
    client = _make_client()
    tone_instructions = {
        "neutral": "Write a balanced, informative comment.",
        "funny": "Write a funny, witty comment with appropriate humor.",
        "supportive": "Write an encouraging, supportive comment.",
        "critical": "Write a thoughtful, constructive critical comment.",
    }
    tone_instruction = tone_instructions.get(tone, tone_instructions["neutral"])
    system = (
        "You are a helpful Reddit commenter. "
        f"{tone_instruction} "
        "Keep the comment concise and relevant. Do not be offensive or violate Reddit rules."
    )
    user = f"Post title: {post_title}"
    if post_body:
        user += f"\n\nPost body: {post_body}"
    if post_context:
        user += f"\n\nContext: {post_context}"
    user += "\n\nWrite a comment for this post."
    return _call_claude(client, system, user)
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_writer.py -v` — expect all passes

---

## Task 6 — Display Helpers (TDD)

**Goal:** Implement `display.py` with formatting functions.

### 6a. Write tests first

Add to a new file `/Users/yorihan/Reddit小工具/tests/test_display.py`:

```python
import io
import sys
from datetime import datetime
from unittest.mock import patch
from reddit_toolkit.display import print_posts, print_subreddits, print_text


SAMPLE_POST = {
    "title": "Test Post Title",
    "score": 500,
    "url": "https://example.com",
    "subreddit": "python",
    "author": "testuser",
    "num_comments": 42,
    "permalink": "/r/python/comments/abc/test/",
    "created_utc": 1700000000.0,
}

SAMPLE_SUB = {
    "display_name": "python",
    "title": "Python",
    "subscribers": 1468454,
    "description": "The largest Python community.",
    "url": "/r/python/",
}


def capture_stdout(func, *args, **kwargs):
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        func(*args, **kwargs)
    return buf.getvalue()


class TestPrintPosts:
    def test_shows_title(self):
        out = capture_stdout(print_posts, [SAMPLE_POST])
        assert "Test Post Title" in out

    def test_shows_index(self):
        out = capture_stdout(print_posts, [SAMPLE_POST])
        assert "1." in out or "1)" in out

    def test_verbose_shows_score(self):
        out = capture_stdout(print_posts, [SAMPLE_POST], verbose=True)
        assert "500" in out

    def test_verbose_shows_comments(self):
        out = capture_stdout(print_posts, [SAMPLE_POST], verbose=True)
        assert "42" in out

    def test_verbose_shows_human_date(self):
        out = capture_stdout(print_posts, [SAMPLE_POST], verbose=True)
        # created_utc 1700000000 = 2023-11-14
        assert "2023" in out

    def test_non_verbose_no_score(self):
        out = capture_stdout(print_posts, [SAMPLE_POST], verbose=False)
        assert "score" not in out.lower()

    def test_empty_list_no_crash(self):
        out = capture_stdout(print_posts, [])
        assert "no posts" in out.lower() or out == "" or len(out) >= 0  # no crash


class TestPrintSubreddits:
    def test_shows_display_name(self):
        out = capture_stdout(print_subreddits, [SAMPLE_SUB])
        assert "python" in out

    def test_shows_subscribers(self):
        out = capture_stdout(print_subreddits, [SAMPLE_SUB])
        assert "1468454" in out or "1,468,454" in out


class TestPrintText:
    def test_shows_label_and_content(self):
        out = capture_stdout(print_text, "Title Suggestions", "First title")
        assert "Title Suggestions" in out
        assert "First title" in out
```

- [ ] Create the test file
- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_display.py -v` — expect failures

### 6b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/display.py`:

```python
from datetime import datetime, timezone


def _format_timestamp(utc_ts: float) -> str:
    """Convert Unix timestamp to human-readable UTC date string."""
    try:
        dt = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError, TypeError):
        return "unknown date"


def print_posts(posts: list, verbose: bool = False) -> None:
    """Print a numbered list of Reddit posts."""
    if not posts:
        print("No posts found.")
        return
    for i, post in enumerate(posts, 1):
        print(f"{i}. {post['title']}")
        if verbose:
            print(f"   Score: {post['score']}  |  Comments: {post['num_comments']}")
            print(f"   Posted: {_format_timestamp(post['created_utc'])}")
            print(f"   URL: {post.get('url', 'N/A')}")
            print(f"   Author: u/{post.get('author', 'unknown')}")
            print()


def print_subreddits(subreddits: list) -> None:
    """Print a numbered list of subreddits with metadata."""
    if not subreddits:
        print("No subreddits found.")
        return
    for i, sub in enumerate(subreddits, 1):
        subscribers = f"{sub['subscribers']:,}"
        print(f"{i}. r/{sub['display_name']} — {subscribers} subscribers")
        if sub.get("description"):
            desc = sub["description"]
            if len(desc) > 100:
                desc = desc[:97] + "..."
            print(f"   {desc}")


def print_text(label: str, content: str) -> None:
    """Print a labelled text block."""
    print(f"\n=== {label} ===")
    print(content)
    print("=" * (len(label) + 8))
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_display.py -v` — expect all passes

---

## Task 7 — CLI Entry Point (TDD)

**Goal:** Implement `cli.py` with full argparse command tree.

### 7a. Write tests first

Add `/Users/yorihan/Reddit小工具/tests/test_cli.py`:

```python
import sys
import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.cli import main


def run_cli(*args):
    """Run the CLI with given args and return (exit_code, stdout, stderr)."""
    import io
    from contextlib import redirect_stdout, redirect_stderr
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = 0
    with patch("sys.argv", ["reddit-toolkit"] + list(args)):
        try:
            with redirect_stdout(out_buf), redirect_stderr(err_buf):
                main()
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0
    return exit_code, out_buf.getvalue(), err_buf.getvalue()


class TestCLIHelp:
    def test_help_exits_zero(self):
        code, out, err = run_cli("--help")
        assert code == 0
        assert "usage" in out.lower() or "usage" in err.lower()

    def test_no_args_shows_help(self):
        code, out, err = run_cli()
        # Should show help or error with non-zero code
        assert isinstance(code, int)


class TestContentHot:
    def test_content_hot_calls_get_hot_posts(self):
        mock_posts = [{"title": "Post 1", "score": 10, "url": "http://x.com",
                       "subreddit": "python", "author": "u1", "num_comments": 5,
                       "permalink": "/r/python/1", "created_utc": 1700000000.0}]
        with patch("reddit_toolkit.cli.get_hot_posts", return_value=mock_posts) as mock_fn:
            with patch("reddit_toolkit.cli.print_posts"):
                run_cli("content", "hot", "--subreddit", "python", "--limit", "5")
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args
        assert "python" in str(call_kwargs)

    def test_content_hot_default_subreddit_is_all(self):
        with patch("reddit_toolkit.cli.get_hot_posts", return_value=[]) as mock_fn:
            with patch("reddit_toolkit.cli.print_posts"):
                run_cli("content", "hot")
        call_args = mock_fn.call_args
        # default subreddit = "all"
        assert "all" in str(call_args)


class TestContentSearch:
    def test_search_calls_search_posts(self):
        with patch("reddit_toolkit.cli.search_posts", return_value=[]) as mock_fn:
            with patch("reddit_toolkit.cli.print_posts"):
                run_cli("content", "search", "asyncio tutorial")
        mock_fn.assert_called_once()


class TestSubsPopular:
    def test_subs_popular_calls_function(self):
        with patch("reddit_toolkit.cli.get_popular_subreddits", return_value=[]) as mock_fn:
            with patch("reddit_toolkit.cli.print_subreddits"):
                run_cli("subs", "popular")
        mock_fn.assert_called_once()


class TestSubsInfo:
    def test_subs_info_calls_get_info(self):
        sub = {"display_name": "python", "title": "Python", "subscribers": 100,
               "description": "desc", "url": "/r/python/"}
        with patch("reddit_toolkit.cli.get_subreddit_info", return_value=sub):
            code, out, err = run_cli("subs", "info", "python")
        assert "python" in out.lower()


class TestWriteTitle:
    def test_write_title_calls_generate(self):
        with patch("reddit_toolkit.cli.generate_post_title", return_value=["Title 1"]) as mock_fn:
            with patch("reddit_toolkit.cli.print_text"):
                run_cli("write", "title", "--subreddit", "python", "--topic", "asyncio")
        mock_fn.assert_called_once()


class TestErrorHandling:
    def test_reddit_api_error_exits_1(self):
        from reddit_toolkit.reddit_client import RedditAPIError
        with patch("reddit_toolkit.cli.get_hot_posts", side_effect=RedditAPIError("404 not found")):
            code, out, err = run_cli("content", "hot")
        assert code == 1

    def test_writer_config_error_exits_1(self):
        from reddit_toolkit.writer import WriterConfigError
        with patch("reddit_toolkit.cli.generate_post_title", side_effect=WriterConfigError("No key")):
            code, out, err = run_cli("write", "title", "--subreddit", "python", "--topic", "test")
        assert code == 1
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_cli.py -v` — expect failures

### 7b. Implement

Create `/Users/yorihan/Reddit小工具/reddit_toolkit/cli.py`:

```python
import argparse
import sys

from .content import get_hot_posts, get_top_posts, get_rising_posts, search_posts
from .subreddits import get_popular_subreddits, search_subreddits, get_subreddit_info, explore_by_topic
from .writer import generate_post_title, write_post_body, generate_comment, WriterConfigError
from .reddit_client import RedditAPIError
from .display import print_posts, print_subreddits, print_text
import requests


def _handle_error(msg: str, exit_code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def cmd_content_hot(args):
    try:
        posts = get_hot_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_top(args):
    try:
        posts = get_top_posts(subreddit=args.subreddit, limit=args.limit, timeframe=args.time)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_rising(args):
    try:
        posts = get_rising_posts(subreddit=args.subreddit, limit=args.limit)
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_content_search(args):
    try:
        posts = search_posts(
            query=args.query,
            subreddit=args.subreddit,
            limit=args.limit,
            sort=args.sort,
        )
        print_posts(posts, verbose=args.verbose)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_popular(args):
    try:
        subs = get_popular_subreddits(limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_search(args):
    try:
        subs = search_subreddits(query=args.query, limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_info(args):
    try:
        sub = get_subreddit_info(args.subreddit)
        print(f"r/{sub['display_name']} — {sub['title']}")
        print(f"Subscribers: {sub['subscribers']:,}")
        print(f"URL: https://www.reddit.com{sub['url']}")
        if sub.get("description"):
            print(f"\nDescription:\n{sub['description']}")
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_subs_explore(args):
    try:
        subs = explore_by_topic(topic=args.topic, limit=args.limit)
        print_subreddits(subs)
    except RedditAPIError as e:
        _handle_error(str(e))
    except requests.exceptions.ConnectionError:
        _handle_error("Network error: could not connect to Reddit.")


def cmd_write_title(args):
    try:
        titles = generate_post_title(
            subreddit=args.subreddit,
            topic=args.topic,
            context=args.context or "",
        )
        print_text("Post Title Suggestions", "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1)))
    except WriterConfigError as e:
        _handle_error(str(e))


def cmd_write_body(args):
    try:
        body = write_post_body(
            subreddit=args.subreddit,
            title=args.title,
            context=args.context or "",
        )
        print_text("Post Body", body)
    except WriterConfigError as e:
        _handle_error(str(e))


def cmd_write_comment(args):
    try:
        comment = generate_comment(
            post_title=args.post_title,
            post_body=args.post_body or "",
            tone=args.tone,
        )
        print_text("Comment", comment)
    except WriterConfigError as e:
        _handle_error(str(e))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reddit-toolkit",
        description="Discover Reddit content, explore subreddits, and write Reddit posts.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- content ---
    content_parser = subparsers.add_parser("content", help="Discover Reddit posts")
    content_sub = content_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # content hot
    hot_p = content_sub.add_parser("hot", help="Hot posts")
    hot_p.add_argument("--subreddit", "-s", default="all", help="Subreddit name (default: all)")
    hot_p.add_argument("--limit", "-n", type=int, default=10, help="Number of posts (default: 10)")
    hot_p.add_argument("--verbose", "-v", action="store_true", help="Show score, comments, date, URL")
    hot_p.set_defaults(func=cmd_content_hot)

    # content top
    top_p = content_sub.add_parser("top", help="Top posts")
    top_p.add_argument("--subreddit", "-s", default="all")
    top_p.add_argument("--limit", "-n", type=int, default=10)
    top_p.add_argument("--time", "-t", default="week",
                       choices=["hour", "day", "week", "month", "year", "all"],
                       help="Time filter (default: week)")
    top_p.add_argument("--verbose", "-v", action="store_true")
    top_p.set_defaults(func=cmd_content_top)

    # content rising
    rising_p = content_sub.add_parser("rising", help="Rising posts")
    rising_p.add_argument("--subreddit", "-s", default="all")
    rising_p.add_argument("--limit", "-n", type=int, default=10)
    rising_p.add_argument("--verbose", "-v", action="store_true")
    rising_p.set_defaults(func=cmd_content_rising)

    # content search
    search_p = content_sub.add_parser("search", help="Search posts")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--subreddit", "-s", default=None,
                          help="Restrict to subreddit (optional)")
    search_p.add_argument("--limit", "-n", type=int, default=10)
    search_p.add_argument("--sort", default="relevance",
                          choices=["relevance", "hot", "top", "new", "comments"])
    search_p.add_argument("--verbose", "-v", action="store_true")
    search_p.set_defaults(func=cmd_content_search)

    # --- subs ---
    subs_parser = subparsers.add_parser("subs", help="Discover subreddits")
    subs_sub = subs_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # subs popular
    pop_p = subs_sub.add_parser("popular", help="List popular subreddits")
    pop_p.add_argument("--limit", "-n", type=int, default=20)
    pop_p.set_defaults(func=cmd_subs_popular)

    # subs search
    ss_p = subs_sub.add_parser("search", help="Search subreddits")
    ss_p.add_argument("query", help="Search query")
    ss_p.add_argument("--limit", "-n", type=int, default=10)
    ss_p.set_defaults(func=cmd_subs_search)

    # subs info
    si_p = subs_sub.add_parser("info", help="Get subreddit info")
    si_p.add_argument("subreddit", help="Subreddit name")
    si_p.set_defaults(func=cmd_subs_info)

    # subs explore
    se_p = subs_sub.add_parser("explore", help="Explore subreddits by topic")
    se_p.add_argument("topic", help="Topic to explore")
    se_p.add_argument("--limit", "-n", type=int, default=10)
    se_p.set_defaults(func=cmd_subs_explore)

    # --- write ---
    write_parser = subparsers.add_parser("write", help="AI-powered writing assistance")
    write_sub = write_parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # write title
    wt_p = write_sub.add_parser("title", help="Generate post title suggestions")
    wt_p.add_argument("--subreddit", "-s", required=True, help="Target subreddit")
    wt_p.add_argument("--topic", "-t", required=True, help="Post topic")
    wt_p.add_argument("--context", "-c", default="", help="Additional context")
    wt_p.set_defaults(func=cmd_write_title)

    # write body
    wb_p = write_sub.add_parser("body", help="Generate post body")
    wb_p.add_argument("--subreddit", "-s", required=True)
    wb_p.add_argument("--title", required=True, help="Post title")
    wb_p.add_argument("--context", "-c", default="")
    wb_p.set_defaults(func=cmd_write_body)

    # write comment
    wc_p = write_sub.add_parser("comment", help="Generate a comment")
    wc_p.add_argument("--post-title", required=True, help="Title of the post to comment on")
    wc_p.add_argument("--post-body", default="", help="Body of the post (optional)")
    wc_p.add_argument("--tone", default="neutral",
                      choices=["neutral", "funny", "supportive", "critical"])
    wc_p.set_defaults(func=cmd_write_comment)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] Run `python3 -m pytest /Users/yorihan/Reddit小工具/tests/test_cli.py -v` — expect all passes

---

## Task 8 — Full Test Suite & Final Verification

**Goal:** All tests pass; CLI is functional end-to-end.

- [ ] Run full test suite:
  ```bash
  python3 -m pytest /Users/yorihan/Reddit小工具/tests/ -v
  ```
  Expect: all tests in `test_reddit_client.py`, `test_content.py`, `test_subreddits.py`, `test_writer.py`, `test_display.py`, `test_cli.py` pass

- [ ] Verify `reddit-toolkit` command is installed and works:
  ```bash
  reddit-toolkit --help
  reddit-toolkit content --help
  reddit-toolkit subs --help
  reddit-toolkit write --help
  ```

- [ ] Smoke test content discovery (requires network):
  ```bash
  reddit-toolkit content hot --subreddit python --limit 3 --verbose
  reddit-toolkit content top --subreddit programming --limit 5 --time week
  reddit-toolkit subs popular --limit 5
  reddit-toolkit subs search "machine learning" --limit 3
  ```

- [ ] Smoke test writing (requires `ANTHROPIC_API_KEY`):
  ```bash
  export ANTHROPIC_API_KEY=your_key_here
  reddit-toolkit write title --subreddit python --topic "asyncio best practices"
  reddit-toolkit write comment --post-title "What's your favorite Python library?" --tone supportive
  ```

- [ ] Verify error handling: unset `ANTHROPIC_API_KEY`, run `reddit-toolkit write title --subreddit python --topic test` — should print error message and exit 1

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Project scaffold + pyproject.toml | Manual verification |
| 2 | `reddit_client.py` — HTTP wrapper | 4 unit tests |
| 3 | `content.py` — post discovery | 8 unit tests |
| 4 | `subreddits.py` — subreddit discovery | 7 unit tests |
| 5 | `writer.py` — Claude-powered writing | 7 unit tests |
| 6 | `display.py` — output formatting | 9 unit tests |
| 7 | `cli.py` — argparse entry point | 10 unit tests |
| 8 | Full suite + smoke tests | Integration |

**Total: 8 tasks, ~45 unit tests**
