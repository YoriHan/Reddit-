import os
import pytest
from unittest.mock import patch, MagicMock
from reddit_toolkit.writer import (
    generate_post_title, write_post_body, generate_comment, WriterConfigError,
    score_post_for_product, generate_opportunity_draft,
    extract_profile_from_text, recommend_subreddits,
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


class TestScorePostForProduct:
    def test_returns_score_dict(self):
        mock_client = make_anthropic_mock('{"score": 8, "hook_angle": "relevant", "reasoning": "matches"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = score_post_for_product(
                    {"title": "test", "subreddit": "python", "score": 100, "num_comments": 10, "selftext": ""},
                    {"name": "MyApp", "description": "...", "problem_solved": "", "keywords": []}
                )
        assert result["score"] == 8
        assert isinstance(result["hook_angle"], str)

    def test_parse_error_returns_zero_score(self):
        mock_client = make_anthropic_mock("not json")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = score_post_for_product(
                    {"title": "t", "subreddit": "s", "score": 0, "num_comments": 0, "selftext": ""}, {}
                )
        assert result["score"] == 0
        assert result["reasoning"] == "parse error"


class TestGenerateOpportunityDraft:
    def test_returns_title_and_body(self):
        mock_client = make_anthropic_mock('{"title": "A title", "body": "A body"}')
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("reddit_toolkit.writer._make_client", return_value=mock_client):
                result = generate_opportunity_draft(
                    {"title": "t", "subreddit": "python", "score": 100, "num_comments": 5},
                    {"name": "MyApp", "description": "...", "tone": "casual"},
                    "hook"
                )
        assert result["title"] == "A title"
        assert result["body"] == "A body"
