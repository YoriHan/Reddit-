import re
import sys
import time

import schedule as _schedule

from .profile_store import load as load_profile, ProfileNotFoundError
from .subreddit_tracker import list_tracked, load_tracked
from .pipeline import discover_subreddits, run_pipeline


def cmd_pipeline_run(args):
    """Run the full pipeline: discover → learn → generate → push to Notion."""
    try:
        load_profile(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        results = run_pipeline(
            args.product,
            push_notion=not args.dry_run,
            force_learn=getattr(args, "force", False),
        )
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ 完成：{len(results)} 篇帖子已生成" + ("并推送到 Notion" if not args.dry_run else "（dry-run）"))


def cmd_pipeline_discover(args):
    """Discover subreddits for a product and update the tracked list."""
    try:
        from .writer import WriterConfigError
        candidates, added = discover_subreddits(args.product, limit=args.limit)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n通过验证：{len(candidates)} 个，新增 {added} 个\n")
    for s in list_tracked(args.product):
        subs = s.get("subscribers", 0)
        subs_label = f"{subs:,}" if subs else "未知"
        print(f"  r/{s['name']}  ({subs_label} 订阅)")
        print(f"    原因: {s['why']}")
        print(f"    加入: {s['added_at'][:10]}")


def cmd_pipeline_list(args):
    """List tracked subreddits for a product."""
    subs = list_tracked(args.product)
    if not subs:
        print(f"'{args.product}' 还没有追踪的 subreddits。")
        print(f"运行: reddit-toolkit pipeline discover --product {args.product}")
        return
    data = load_tracked(args.product)
    last = data.get("last_discovery", "")[:10]
    print(f"r/{args.product} 追踪的 subreddits（上次发现: {last}）：\n")
    for s in subs:
        print(f"  r/{s['name']}")
        print(f"    原因: {s['why']}")
        print(f"    加入: {s['added_at'][:10]}")


def cmd_pipeline_daemon(args):
    """Run pipeline on a schedule (e.g. every 1d, 8h, 30m)."""
    m = re.fullmatch(r"(\d+)(h|m|d)", args.interval)
    if not m:
        print(f"Error: 无效的时间间隔 '{args.interval}'，请使用如 1d、8h、30m。", file=sys.stderr)
        sys.exit(1)
    n, unit = int(m.group(1)), m.group(2)

    def job():
        print(f"\n{'='*50}")
        print(f"Pipeline 开始运行 — {args.product}")
        print(f"{'='*50}")
        try:
            run_pipeline(args.product, push_notion=True)
        except Exception as e:
            print(f"Pipeline error: {e}", file=sys.stderr)

    if unit == "h":
        _schedule.every(n).hours.do(job)
    elif unit == "m":
        _schedule.every(n).minutes.do(job)
    else:
        _schedule.every(n).days.do(job)

    interval_label = {"h": f"{n}小时", "m": f"{n}分钟", "d": f"{n}天"}[unit]
    print(f"Pipeline daemon 已启动。每 {interval_label} 运行一次。Ctrl+C 停止。\n")
    job()  # 立即运行一次
    try:
        while True:
            _schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nDaemon 已停止。")
        sys.exit(0)
