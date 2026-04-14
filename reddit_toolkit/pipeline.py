"""
Full content pipeline for a product:
  1. Discover subreddits via AI
  2. For each tracked subreddit: learn style + rules
  3. Generate a mimic post
  4. Push post to Notion (Reddit素材 database)
  5. Push rules to Notion (Subreddit规则 database)
"""
import sys

from .profile_store import load as load_profile
from .style_store import load as load_style, is_stale, StyleNotFoundError, save as save_style
from .style_learner import fetch_subreddit_corpus
from .writer import (
    recommend_subreddits, analyze_subreddit_style,
    generate_mimic_post, WriterConfigError,
)
from .rules_store import load as load_rules, is_stale_norms, RulesNotFoundError, save as save_rules
from .rules_learner import learn_rules, RulesInferenceError
from .subreddit_tracker import add_subreddits, list_tracked
from .subreddits import validate_subreddit_for_promotion


def _validate_and_filter(candidates: list, min_subscribers: int = 5000) -> tuple:
    """Check each AI-recommended subreddit against the real Reddit API.

    Returns (validated_candidates, rejected_list).
    Each validated candidate gets enriched with 'subscribers' and 'active_users'.
    Candidates are sorted by subscriber count (descending).
    """
    validated = []
    rejected = []
    for c in candidates:
        name = c.get("name", "")
        if not name:
            continue
        result = validate_subreddit_for_promotion(name, min_subscribers=min_subscribers)
        if result.get("ok"):
            validated.append({
                **c,
                "subscribers": result.get("subscribers", 0),
                "active_users": result.get("active_users", 0),
            })
        else:
            rejected.append({"name": name, "reason": result.get("reason", "")})
    validated.sort(key=lambda x: x.get("subscribers", 0), reverse=True)
    return validated, rejected


def discover_subreddits(product_id: str, limit: int = 30) -> tuple:
    """Ask AI to recommend subreddits for the product, validate against Reddit API, then track.

    Returns (validated_candidates, newly_added_count).
    """
    profile = load_profile(product_id)
    print(f"  AI 生成 {limit} 个候选...", flush=True)
    candidates = recommend_subreddits(profile, limit=limit)
    print(f"  验证 {len(candidates)} 个候选（检查订阅数 + 是否公开）...", flush=True)
    validated, rejected = _validate_and_filter(candidates)
    if rejected:
        print(f"  过滤掉 {len(rejected)} 个：" + ", ".join(
            f"r/{r['name']}({r['reason']})" for r in rejected
        ), flush=True)
    added = add_subreddits(product_id, validated)
    return validated, added


def _learn_sub(sub_name: str, force: bool = False) -> tuple:
    """Learn style + rules for a subreddit. Returns (style_cache, rules_data)."""
    # Style
    try:
        style_cache = load_style(sub_name)
        need_style = force or is_stale(style_cache)
    except StyleNotFoundError:
        need_style = True

    posts = None
    if need_style:
        print(f"    学习写作风格...", flush=True)
        posts = fetch_subreddit_corpus(sub_name, pages=5)
        style_data = analyze_subreddit_style(sub_name, posts)
        style_cache = {"posts_analyzed": len(posts), "pages_fetched": 5, "style": style_data}
        save_style(sub_name, style_cache)

    # Rules
    try:
        rules_data = load_rules(sub_name)
        need_rules = force or is_stale_norms(rules_data)
    except RulesNotFoundError:
        need_rules = True

    if need_rules:
        print(f"    学习社群规则...", flush=True)
        try:
            rules_data = learn_rules(sub_name, posts=posts)
            save_rules(sub_name, rules_data)
        except RulesInferenceError as e:
            print(f"    警告：规则推断失败: {e}", file=sys.stderr)
            rules_data = None
    else:
        rules_data = load_rules(sub_name)

    return style_cache, rules_data


def run_pipeline(product_id: str, push_notion: bool = True, force_learn: bool = False) -> list:
    """
    Full pipeline for a product. Returns list of {subreddit, result} dicts.
    push_notion=True → push posts to Reddit素材 + rules to Subreddit规则
    """
    profile = load_profile(product_id)

    # Step 1: Discover subreddits
    print(f"发现适合 {profile['name']} 的 subreddits...", flush=True)
    candidates, added = discover_subreddits(product_id)
    tracked = list_tracked(product_id)
    print(f"  追踪中：{len(tracked)} 个 subreddits（新增 {added} 个）")

    results = []

    for sub in tracked:
        sub_name = sub["name"]
        print(f"\n─── r/{sub_name} ───", flush=True)

        # Step 2: Learn
        try:
            style_cache, rules_data = _learn_sub(sub_name, force=force_learn)
        except WriterConfigError as e:
            print(f"  Error: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  学习失败: {e}", file=sys.stderr)
            continue

        # Step 3: Push rules to Notion
        if push_notion and rules_data:
            try:
                from .notion_pusher import push_rules_profile, NotionConfigError
                push_rules_profile(sub_name, rules_data)
                print(f"  规则已更新到 Notion", flush=True)
            except Exception as e:
                print(f"  规则 Notion 推送失败: {e}", file=sys.stderr)

        # Step 4: Generate post
        print(f"  生成帖子...", flush=True)
        try:
            result = generate_mimic_post(
                sub_name,
                style_cache["style"],
                profile,
                rules=rules_data,
            )
        except WriterConfigError as e:
            print(f"  Error: {e}", file=sys.stderr)
            continue

        results.append({"subreddit": sub_name, "result": result})
        print(f"  标题：{result['title'][:60]}", flush=True)

        # Step 5: Push post to Notion (Reddit素材)
        if push_notion:
            try:
                from .notion_pusher import push_mimic_post, NotionConfigError
                push_mimic_post(profile, sub_name, result)
                print(f"  帖子已推送到 Notion ✓", flush=True)
            except Exception as e:
                print(f"  帖子 Notion 推送失败: {e}", file=sys.stderr)

    return results
