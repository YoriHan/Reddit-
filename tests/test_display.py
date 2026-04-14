import io
from datetime import datetime
from rich.console import Console
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


def capture(func, *args, **kwargs):
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    func(*args, **kwargs, console=console)
    return buf.getvalue()


class TestPrintPosts:
    def test_shows_title(self):
        out = capture(print_posts, [SAMPLE_POST])
        assert "Test Post Title" in out

    def test_shows_index(self):
        out = capture(print_posts, [SAMPLE_POST])
        assert "1" in out

    def test_verbose_shows_score(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "500" in out

    def test_verbose_shows_comments(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "42" in out

    def test_verbose_shows_human_date(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=True)
        assert "2023" in out

    def test_non_verbose_no_score(self):
        out = capture(print_posts, [SAMPLE_POST], verbose=False)
        assert "500" not in out

    def test_empty_list_no_crash(self):
        out = capture(print_posts, [])
        assert len(out) >= 0  # no crash


class TestPrintSubreddits:
    def test_shows_display_name(self):
        out = capture(print_subreddits, [SAMPLE_SUB])
        assert "python" in out

    def test_shows_subscribers(self):
        out = capture(print_subreddits, [SAMPLE_SUB])
        assert "1468454" in out or "1,468,454" in out


class TestPrintText:
    def test_shows_label_and_content(self):
        out = capture(print_text, "Title Suggestions", "First title")
        assert "Title Suggestions" in out
        assert "First title" in out
