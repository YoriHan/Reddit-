import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import schedule as _schedule

from .profile_store import load, ProfileNotFoundError
from .scanner import run_scan


def cmd_scan_run(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Best-effort: ensure rules are cached for each target subreddit
    from .rules_store import load as load_rules, is_stale_norms, RulesNotFoundError
    from .rules_learner import learn_rules, RulesInferenceError
    from .rules_store import save as save_rules
    for sub in profile.get("subreddits", []):
        sub_name = sub["name"] if isinstance(sub, dict) else sub
        try:
            existing = load_rules(sub_name)
            if not is_stale_norms(existing):
                continue
        except RulesNotFoundError:
            pass
        try:
            rules_data = learn_rules(sub_name)
            save_rules(sub_name, rules_data)
        except Exception:
            pass  # non-fatal: scan proceeds without rules

    result = run_scan(
        profile=profile,
        dry_run=args.dry_run,
        top_n=args.top,
        threshold=args.threshold,
    )
    print(f"\nScan summary:")
    print(f"  Subreddits scanned: {len(result.subreddits)}")
    print(f"  Posts fetched: {result.total_fetched}")
    print(f"  New posts scored: {result.new_posts}")
    print(f"  Opportunities found: {len(result.opportunities)}")
    if args.dry_run:
        for opp in result.opportunities:
            print(f"\n  [{opp['score_result']['score']}/10] {opp['post']['title']}")
            print(f"  Hook: {opp['score_result']['hook_angle']}")
            print(f"  Draft title: {opp['draft']['title']}")

    if getattr(args, "notion", False) and not args.dry_run:
        from .notion_pusher import push_scan_results, NotionConfigError
        try:
            push_scan_results(profile, result)
            print(f"  Pushed to Notion: {len(result.opportunities) or 1} page(s)")
        except NotionConfigError as e:
            print(f"  Notion push failed: {e}", file=sys.stderr)


def cmd_scan_show(args):
    state_dir = Path(os.environ.get("REDDIT_TOOLKIT_DATA_DIR", "~/.reddit-toolkit")).expanduser() / "state"
    path = state_dir / f"{args.product}.opportunities.jsonl"
    if not path.exists():
        print(f"No scan history for '{args.product}'.")
        return
    lines = path.read_text().strip().split("\n")
    lines = [l for l in lines if l]
    recent = lines[-(args.last):]
    for line in recent:
        try:
            opp = json.loads(line)
            print(f"[{opp['scanned_at'][:10]}] [{opp['score_result']['score']}/10] {opp['post']['title']}")
        except Exception:
            continue


def cmd_scan_daemon(args):
    m = re.fullmatch(r"(\d+)(h|m|d)", args.interval)
    if not m:
        print(f"Error: invalid interval '{args.interval}'. Use e.g. 8h, 30m, 1d.", file=sys.stderr)
        sys.exit(1)
    n, unit = int(m.group(1)), m.group(2)

    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    def job():
        print(f"\nRunning scan for '{args.product}'...")
        run_scan(profile=profile, dry_run=False, top_n=10, threshold=7.0)
        print("Scan complete.")

    if unit == "h":
        _schedule.every(n).hours.do(job)
    elif unit == "m":
        _schedule.every(n).minutes.do(job)
    else:
        _schedule.every(n).days.do(job)

    print(f"Daemon started. Scanning every {args.interval}. Ctrl+C to stop.")
    try:
        while True:
            _schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")
        sys.exit(0)


def cmd_scan_setup_cron(args):
    binary = shutil.which("reddit-toolkit")
    if not binary:
        binary = "/path/to/reddit-toolkit"
        print("Warning: 'reddit-toolkit' not found in PATH. Replace the path below manually.")
    log_path = f"~/.reddit-toolkit/logs/{args.product}.log"
    line = f"{args.minute} {args.hour} * * * {binary} scan run --product {args.product} >> {log_path} 2>&1"
    print("\nAdd this line to your crontab (run 'crontab -e'):\n")
    print(f"  {line}\n")
