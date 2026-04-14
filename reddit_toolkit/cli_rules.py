import sys

from .rules_store import load, list_rules, is_stale_norms, is_stale_rules, RulesNotFoundError
from .rules_learner import learn_rules, RulesInferenceError
from .rules_store import save


def cmd_rules_learn(args):
    try:
        existing = load(args.subreddit)
        if not args.force and not is_stale_norms(existing):
            print(f"Rules for r/{args.subreddit} are fresh. Use --force to re-learn.")
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
    checklist = norms.get("posting_checklist", [])
    print(f"\nRules profile saved for r/{args.subreddit}.")
    print(f"  Official rules: {n_official}")
    print(f"  Tone: {norms.get('tone_guidelines', 'N/A')[:80]}")
    print(f"  Posting checklist: {len(checklist)} items")


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
