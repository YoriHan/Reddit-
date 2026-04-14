import os
import json as _json
import anthropic


class WriterConfigError(Exception):
    """Raised when writer configuration is missing (e.g. no API key)."""
    pass


def _make_client():
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
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
    text = response.content[0].text.strip()
    # Strip markdown code fences if Claude wraps JSON in ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text


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


def match_subreddits_for_topic(profile: dict, topic: str = "", limit: int = 5) -> list:
    """Recommend subreddits fit for a specific product + post topic.

    Returns list of {"name": str, "why": str, "self_promo_tolerance": str, "post_angle": str}
    """
    client = _make_client()
    system = (
        "You are a Reddit community expert. Given a product and a post topic/angle, "
        "recommend subreddits where this post would be genuinely welcomed. "
        "For each, estimate self-promotion tolerance (low/medium/high) based on community culture. "
        "Return a JSON array only — no other text. "
        f'Schema: [{{"name": "subreddit_name_without_r/", "why": "one sentence", '
        f'"self_promo_tolerance": "low|medium|high", "post_angle": "one sentence angle"}}]'
    )
    topic_line = f"\nPost topic/angle: {topic}" if topic else ""
    user = (
        f"Product: {profile.get('name', '')}\n"
        f"Description: {profile.get('description', '')}\n"
        f"Target audience: {', '.join(profile.get('target_audience', []))}\n"
        f"Key features: {', '.join(profile.get('key_features', []))}"
        f"{topic_line}\n\n"
        f"Recommend {limit} subreddits."
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
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        result = _json.loads(raw)
        return {"title": result.get("title", ""), "body": result.get("body", "")}
    except _json.JSONDecodeError:
        return {"title": "", "body": raw[:2000]}


def analyze_subreddit_style(subreddit: str, posts: list) -> dict:
    """Analyze a corpus of Reddit posts and extract the subreddit's writing style.

    Takes up to 200 top-scoring posts, truncates bodies to 100 chars each,
    and asks Claude to identify style patterns.

    Returns:
        dict with keys: tone, formality, common_title_patterns, body_style,
        humor_level, self_promotion_tolerance, taboo_topics, vocabulary_signals,
        community_values, successful_post_traits, raw_title_samples
    """
    client = _make_client()
    top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:200]

    post_lines = []
    for p in top_posts:
        body_preview = (p.get("selftext") or "")[:100].replace("\n", " ")
        post_lines.append(
            f"TITLE: {p['title']} | SCORE: {p['score']} | BODY: {body_preview}"
        )
    corpus_text = "\n".join(post_lines)

    system = (
        "You are a cultural analyst specializing in online communities. "
        "Analyze this Reddit post corpus and extract the community's writing style, "
        "tone, format conventions, and cultural norms. "
        "Return a JSON object only — no other text. "
        'Schema: {"tone": str, "formality": "low|medium|high", '
        '"common_title_patterns": [str], "body_style": str, '
        '"humor_level": str, "self_promotion_tolerance": str, '
        '"taboo_topics": [str], "vocabulary_signals": [str], '
        '"community_values": [str], "successful_post_traits": str, '
        '"raw_title_samples": [str]}'
    )
    user = (
        f"Subreddit: r/{subreddit}\n"
        f"Corpus ({len(top_posts)} posts, sorted by score):\n\n{corpus_text}"
    )
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        return {
            "tone": raw[:200],
            "formality": "low",
            "common_title_patterns": [],
            "body_style": "",
            "humor_level": "",
            "self_promotion_tolerance": "unknown",
            "taboo_topics": [],
            "vocabulary_signals": [],
            "community_values": [],
            "successful_post_traits": "",
            "raw_title_samples": [p["title"] for p in top_posts[:20]],
        }


def generate_mimic_post(
    subreddit: str, style: dict, profile: dict, topic: str = ""
) -> dict:
    """Generate a Reddit post that mimics a subreddit's style while featuring a product.

    Args:
        subreddit: Target subreddit name
        style: Style dict from analyze_subreddit_style
        profile: Product profile dict (from profile_store or inline)
        topic: Optional post angle hint (e.g. 'launch announcement')

    Returns:
        {"title": str, "body": str, "why_it_fits": str}
    """
    client = _make_client()
    title_samples = "\n".join(
        f"- {t}" for t in style.get("raw_title_samples", [])[:10]
    )
    system = (
        f"You are a native r/{subreddit} contributor. Write a Reddit post that fits "
        "this community perfectly — not an ad, but a genuine contribution that "
        "naturally mentions a product where relevant. "
        f"\n\nCommunity style guide:"
        f"\n- Tone: {style.get('tone', 'casual')}"
        f"\n- Formality: {style.get('formality', 'low')}"
        f"\n- Self-promotion tolerance: {style.get('self_promotion_tolerance', 'low')}"
        f"\n- Successful post traits: {style.get('successful_post_traits', '')}"
        f"\n- Common title patterns: {', '.join(style.get('common_title_patterns', []))}"
        f"\n- Community values: {', '.join(style.get('community_values', []))}"
        f"\n- Vocabulary to use naturally: {', '.join(style.get('vocabulary_signals', []))}"
        f"\n- Topics to avoid: {', '.join(style.get('taboo_topics', []))}"
        f"\n\nExample high-performing titles:\n{title_samples}"
        f"\n\nProduct to mention naturally:"
        f"\nName: {profile.get('name', '')}"
        f"\nDescription: {profile.get('description', '')}"
        f"\nProblem solved: {profile.get('problem_solved', '')}"
        f"\nTarget audience: {', '.join(profile.get('target_audience', []))}"
        "\n\nRules:"
        "\n1. Community value first — product mention is secondary"
        "\n2. Product mention must feel incidental, not the headline"
        "\n3. Match vocabulary and formatting exactly as seen in examples"
        "\n4. Respect the self-promotion tolerance level"
        '\nReturn JSON only: {"title": str, "body": str, "why_it_fits": str}'
    )
    post_type = topic if topic else "general contribution"
    user = f"Write a {post_type} post for r/{subreddit} that feels completely native."
    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text
    try:
        result = _json.loads(raw)
        return {
            "title": result.get("title", ""),
            "body": result.get("body", ""),
            "why_it_fits": result.get("why_it_fits", ""),
        }
    except _json.JSONDecodeError:
        return {"title": "", "body": raw[:2000], "why_it_fits": ""}
