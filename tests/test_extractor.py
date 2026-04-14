# tests/test_extractor.py
import os
import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.extractor import read_file, read_codebase


def test_read_file_returns_content(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("Hello world")
    result = read_file(str(f))
    assert "Hello world" in result
    assert "README.md" in result


def test_read_file_truncates(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 10000)
    result = read_file(str(f), max_chars=100)
    assert len(result) < 200  # header + 100 chars


def test_read_codebase_skips_hidden_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret")
    (tmp_path / "README.md").write_text("visible")
    result = read_codebase(str(tmp_path))
    assert "secret" not in result
    assert "visible" in result


def test_read_codebase_respects_max_chars(tmp_path):
    for i in range(5):
        (tmp_path / f"file{i}.md").write_text("y" * 1000)
    result = read_codebase(str(tmp_path), max_chars=2000)
    assert len(result) <= 2500  # some header overhead


class TestReadUrl:
    def test_returns_article_text(self):
        mock_article = MagicMock()
        mock_article.text = "This is a great product for developers."
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article):
            from reddit_toolkit.extractor import read_url
            result = read_url("https://example.com")
        assert result == "This is a great product for developers."
        mock_article.download.assert_called_once()
        mock_article.parse.assert_called_once()

    def test_raises_value_error_on_empty_text(self):
        mock_article = MagicMock()
        mock_article.text = "   "
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article):
            from reddit_toolkit.extractor import read_url
            with pytest.raises(ValueError, match="No article text"):
                read_url("https://example.com/empty")

    def test_url_passed_to_article(self):
        mock_article = MagicMock()
        mock_article.text = "some text"
        with patch("reddit_toolkit.extractor.newspaper.Article", return_value=mock_article) as mock_cls:
            from reddit_toolkit.extractor import read_url
            read_url("https://myproduct.com")
        mock_cls.assert_called_once_with("https://myproduct.com")
