# tests/test_extractor.py
import os
import pytest
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
