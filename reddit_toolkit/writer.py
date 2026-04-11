import os
import json as _json
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


def extract_profile_from_text(raw_text: str, name: str) -> dict:
    """Ask Claude to extract a product profile from raw codebase/README text.

    Returns a dict with keys: description, problem_solved, target_audience,
    key_features, keywords. Keys may be empty strings/lists if not found.
    """
    client = _make_client()
    system = (
        "You are a product analyst. Given text from a software product's codebase or documentation, "
        "extract key product information. Respond with a JSON object only — no other text. "
        'Schema: {"description": str, "problem_solved": str, "target_audience": [str], '
        '"key_features": [str], "keywords": [str]}'
    )
    user = f"Product name: {name}\n\nContent:\n{raw_text[:30000]}"
    raw = _call_claude(client, system, user)
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return {"description": raw[:500], "problem_solved": "", "target_audience": [],
                "key_features": [], "keywords": []}


def recommend_subreddits(profile: dict, limit: int = 10) -> list:
    """Ask Claude to recommend subreddits for a product.

    Returns list of {"name": str, "why": str}.
    """
    client = _make_client()
    system = (
        "You are a Reddit marketing expert. Given a product description, recommend subreddits "
        f"where the product would be naturally relevant to discuss. Return a JSON array of exactly {limit} objects. "
        'Schema: [{"name": "subreddit_name_without_r/", "why": "one sentence reason"}]'
    )
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Target audience: {', '.join(profile.get('target_audience', []))}\n"
        f"Key features: {', '.join(profile.get('key_features', []))}"
    )
    raw = _call_claude(client, system, user)
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return []


def score_post_for_product(post: dict, profile: dict) -> dict:
    """Score a Reddit post's relevance as a marketing opportunity for the product.

    Returns {"score": int (0-10), "hook_angle": str, "reasoning": str}.
    On parse failure returns {"score": 0, "hook_angle": "", "reasoning": "parse error"}.
    """
    client = _make_client()
    system = (
        "You are a Reddit marketing analyst. Score how relevant this Reddit post is as an "
        "opportunity to naturally mention or promote the product. Be strict: only score >= 7 "
        "if the post topic directly relates to a problem the product solves or a feature it has. "
        "Return JSON only. Schema: {\"score\": <int 0-10>, \"hook_angle\": \"<one sentence>\", "
        "\"reasoning\": \"<one sentence>\"}"
    )
    selftext_preview = (post.get("selftext") or "")[:500]
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Problem solved: {profile.get('problem_solved', '')}\n"
        f"Keywords: {', '.join(profile.get('keywords', []))}\n\n"
        f"Reddit post:\n"
        f"Title: {post.get('title', '')}\n"
        f"Subreddit: r/{post.get('subreddit', '')}\n"
        f"Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}\n"
        f"Body preview: {selftext_preview}"
    )
    raw = _call_claude(client, system, user)
    try:
        result = _json.loads(raw)
        return {
            "score": int(result.get("score", 0)),
            "hook_angle": result.get("hook_angle", ""),
            "reasoning": result.get("reasoning", ""),
        }
    except (_json.JSONDecodeError, ValueError):
        return {"score": 0, "hook_angle": "", "reasoning": "parse error"}


def generate_opportunity_draft(post: dict, profile: dict, hook_angle: str) -> dict:
    """Generate a Reddit post draft for a marketing opportunity.

    Returns {"title": str, "body": str}.
    """
    client = _make_client()
    system = (
        f"You are a Reddit marketing expert writing for r/{post.get('subreddit', 'all')}. "
        "Write a genuine Reddit post that contributes value to the discussion first, then "
        "naturally mentions the product where relevant. The post must feel organic — not an ad. "
        f"Tone: {profile.get('tone', 'casual')}. Max 300 words for the body. "
        "Return JSON only. Schema: {\"title\": str, \"body\": str}"
    )
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Product description: {profile.get('description', '')}\n"
        f"Hook angle: {hook_angle}\n\n"
        f"Trending post to respond to:\n"
        f"Title: {post.get('title', '')}\n"
        f"r/{post.get('subreddit', '')} | {post.get('score', 0)} upvotes | "
        f"{post.get('num_comments', 0)} comments"
    )
    # Use higher token budget for draft generation (2048 instead of default 1024)
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text
    try:
        result = _json.loads(raw)
        return {"title": result.get("title", ""), "body": result.get("body", "")}
    except _json.JSONDecodeError:
        return {"title": "", "body": raw[:2000]}
