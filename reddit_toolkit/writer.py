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


def _call_claude(client, system_prompt: str, user_prompt: str) -> str:
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
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
    user = f"Subreddit: r/{subreddit}\nGenerate post titles about: {topic}"
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
    user = f"Tone: {tone}\nPost title: {post_title}"
    if post_body:
        user += f"\n\nPost body: {post_body}"
    if post_context:
        user += f"\n\nContext: {post_context}"
    user += "\n\nWrite a comment for this post."
    return _call_claude(client, system, user)
