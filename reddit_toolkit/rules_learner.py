import json
import os
from datetime import datetime, timezone

from .reddit_client import RedditClient, RedditAPIError
from .style_learner import fetch_subreddit_corpus


class RulesInferenceError(Exception):
    pass


_NORMS_SYSTEM = (
    "You are a Reddit community analyst. Analyze these posts and infer the implicit "
    "community norms — what gets removed, what's welcome, unwritten rules, and the overall vibe. "
    "Respond entirely in Simplified Chinese. Return JSON only, no other text. "
    'Schema: {"社群氛围": str, "社群价值观": [str], '
    '"会被删除的内容": [str], "发帖检查清单": [str], '
    '"安全发帖角度": [str], "外链规则": str, '
    '"整体氛围观察": str}'
)


def fetch_official_rules(subreddit: str, client=None) -> list:
    """GET /r/{subreddit}/about/rules.json → list of {short_name, description, priority}."""
    c = client if client is not None else RedditClient()
    try:
        response = c.get(f"/r/{subreddit}/about/rules.json")
        rules = response.get("rules", [])
        return [
            {
                "short_name": r.get("short_name", ""),
                "description": r.get("description", ""),
                "priority": r.get("priority", 0),
            }
            for r in rules
        ]
    except (RedditAPIError, KeyError, Exception):
        return []


def infer_norms(subreddit: str, posts: list, ai_client=None) -> tuple:
    """Call Claude with post corpus → inferred_norms dict. Raises RulesInferenceError on failure."""
    from .writer import _make_client as _make_writer_client
    client = ai_client or _make_writer_client()

    top_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:100]
    lines = [
        f"SCORE:{p['score']} TITLE:{p['title']} BODY:{(p.get('selftext') or '')[:80]}"
        for p in top_posts
    ]
    user = f"Subreddit: r/{subreddit}\n\n" + "\n".join(lines)

    response = client.messages.create(
        model=os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
        max_tokens=2048,
        system=_NORMS_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines_r = raw.splitlines()
        raw = "\n".join(lines_r[1:-1] if lines_r[-1].strip() == "```" else lines_r[1:])

    try:
        norms = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RulesInferenceError(
            f"AI returned invalid JSON for r/{subreddit} norm inference: {e}\n"
            "Try: reddit-toolkit rules learn --force --subreddit " + subreddit
        ) from e

    required = {"社群氛围", "社群价值观", "会被删除的内容", "发帖检查清单", "安全发帖角度", "外链规则", "整体氛围观察"}
    missing = required - set(norms.keys())
    if missing:
        raise RulesInferenceError(
            f"AI response missing required keys: {missing}. "
            "Try: reddit-toolkit rules learn --force --subreddit " + subreddit
        )

    tokens = getattr(response.usage, "input_tokens", 0) + getattr(response.usage, "output_tokens", 0)
    return norms, tokens


def learn_rules(subreddit: str, posts: list = None, reddit_client=None, ai_client=None) -> dict:
    """Orchestrate: fetch official rules + infer norms. Returns full rules dict."""
    now = datetime.now(timezone.utc).isoformat()

    official = fetch_official_rules(subreddit, client=reddit_client)
    rules_fetched_at = now

    if posts is None:
        posts = fetch_subreddit_corpus(subreddit, pages=5, client=reddit_client)

    norms, tokens = infer_norms(subreddit, posts, ai_client=ai_client)
    norms_learned_at = datetime.now(timezone.utc).isoformat()

    return {
        "subreddit": subreddit.lower(),
        "rules_fetched_at": rules_fetched_at,
        "norms_learned_at": norms_learned_at,
        "official_rules": official,
        "inferred_norms": norms,
        "inference_metadata": {
            "posts_analyzed": len(posts),
            "norms_model_used": os.environ.get("REDDIT_TOOLKIT_MODEL", "claude-opus-4-5"),
            "inference_token_cost": tokens,
        },
    }
