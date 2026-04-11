import json
import os
import shutil
import sys
from pathlib import Path

from .profile_store import load, ProfileNotFoundError
from .scanner import run_scan


def cmd_scan_run(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

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


def cmd_scan_setup_cron(args):
    binary = shutil.which("reddit-toolkit")
    if not binary:
        binary = "/path/to/reddit-toolkit"
        print("Warning: 'reddit-toolkit' not found in PATH. Replace the path below manually.")
    log_path = f"~/.reddit-toolkit/logs/{args.product}.log"
    line = f"{args.minute} {args.hour} * * * {binary} scan run --product {args.product} >> {log_path} 2>&1"
    print("\nAdd this line to your crontab (run 'crontab -e'):\n")
    print(f"  {line}\n")
