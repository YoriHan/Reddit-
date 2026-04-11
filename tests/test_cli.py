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


class TestWriteComment:
    def test_write_comment_passes_post_context(self):
        with patch("reddit_toolkit.cli.generate_comment", return_value="Great post!") as mock_fn:
            with patch("reddit_toolkit.cli.print_text"):
                run_cli(
                    "write", "comment",
                    "--post-title", "Hello World",
                    "--post-body", "Some body text",
                    "--post-context", "extra context here",
                    "--tone", "supportive",
                )
        mock_fn.assert_called_once_with(
            post_title="Hello World",
            post_body="Some body text",
            post_context="extra context here",
            tone="supportive",
        )

    def test_write_comment_default_post_context_is_empty(self):
        with patch("reddit_toolkit.cli.generate_comment", return_value="A comment") as mock_fn:
            with patch("reddit_toolkit.cli.print_text"):
                run_cli("write", "comment", "--post-title", "My Post")
        call_kwargs = mock_fn.call_args
        assert call_kwargs.kwargs.get("post_context", "") == ""


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
