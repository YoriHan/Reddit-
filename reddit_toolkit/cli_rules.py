import sys

from .rules_store import load, list_rules, is_stale_norms, is_stale_rules, RulesNotFoundError
from .rules_learner import learn_rules, RulesInferenceError
from .rules_store import save


def cmd_rules_learn(args):
    try:
        existing = load(args.subreddit)
        if not args.force and not is_stale_norms(existing):
            print(f"Rules for r/{args.subreddit} are fresh. Use --force to re-learn.")
            if getattr(args, "notion", False):
                _push_to_notion(args.subreddit, existing)
            return
    except RulesNotFoundError:
        pass

    print(f"Fetching official rules for r/{args.subreddit}...")
    try:
        data = learn_rules(args.subreddit)
        save(args.subreddit, data)
    except RulesInferenceError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    n_official = len(data.get("official_rules", []))
    norms = data.get("inferred_norms", {})
    checklist = norms.get("发帖检查清单", [])
    print(f"\nRules profile saved for r/{args.subreddit}.")
    print(f"  官方规则: {n_official} 条")
    print(f"  社群氛围: {norms.get('社群氛围', 'N/A')[:80]}")
    print(f"  发帖检查清单: {len(checklist)} 项")

    if getattr(args, "notion", False):
        _push_to_notion(args.subreddit, data)


def _push_to_notion(subreddit: str, data: dict) -> None:
    from .notion_pusher import push_rules_profile, NotionConfigError
    try:
        url = push_rules_profile(subreddit, data)
        print(f"  Notion page updated: {url}")
    except NotionConfigError as e:
        print(f"  Notion push failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  Notion push failed: {e}", file=sys.stderr)


def cmd_rules_notion_setup(args):
    from .notion_pusher import save_rules_parent_page_id
    page_id = args.page_id.split("?")[0].rstrip("/").split("/")[-1].replace("-", "")
    # Normalize to UUID format with dashes
    if len(page_id) == 32:
        page_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
    save_rules_parent_page_id(page_id)
    print(f"Rules Notion parent page set: {page_id}")


def cmd_rules_show(args):
    import json
    try:
        data = load(args.subreddit)
    except RulesNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, indent=2))


def cmd_rules_list(args):
    all_rules = list_rules()
    if not all_rules:
        print("No rules profiles cached. Run: reddit-toolkit rules learn --subreddit <name>")
        return
    for r in all_rules:
        stale = " [STALE]" if is_stale_norms(r) else ""
        learned = r.get("norms_learned_at", "")[:10]
        n = len(r.get("official_rules", []))
        print(f"  r/{r.get('subreddit', '?')} — {n} official rules — learned {learned}{stale}")
