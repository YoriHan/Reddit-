import json
import sys

from .profile_store import new_profile, save, load, list_profiles, ProfileNotFoundError
from .writer import extract_profile_from_text, recommend_subreddits, WriterConfigError
from .extractor import read_file, read_codebase, read_url


def cmd_product_create(args):
    profile = new_profile(args.name)

    raw_text = ""
    if args.from_dir:
        print(f"Reading codebase from {args.from_dir}...")
        raw_text = read_codebase(args.from_dir)
    elif args.from_file:
        print(f"Reading file {args.from_file}...")
        raw_text = read_file(args.from_file)
    elif args.from_url:
        print(f"Fetching article from {args.from_url}...")
        try:
            raw_text = read_url(args.from_url)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.description:
        raw_text = args.description

    if raw_text:
        print("Extracting product profile with AI...")
        try:
            extracted = extract_profile_from_text(raw_text, args.name)
        except WriterConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        for key in ("description", "problem_solved", "target_audience", "key_features", "keywords"):
            if extracted.get(key):
                profile[key] = extracted[key]

    print("\nDraft profile:")
    print(json.dumps(profile, indent=2))
    if not getattr(args, "yes", False):
        try:
            confirm = input("\nSave? [y/N]: ").strip().lower()
        except EOFError:
            confirm = "y"
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    save(profile)
    print(f"Saved profile '{profile['id']}'.")


def cmd_product_list(args):
    profiles = list_profiles()
    if not profiles:
        print("No products configured.")
        return
    for p in profiles:
        sub_count = len(p.get("subreddits", []))
        print(f"  {p['id']} — {p['name']} ({sub_count} subreddits)")


def cmd_product_show(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(profile, indent=2))


def cmd_product_add_subreddit(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    profile.setdefault("subreddits", []).append({
        "name": args.subreddit,
        "why": args.why or "",
        "added_by": "user",
    })
    save(profile)
    print(f"Added r/{args.subreddit} to {args.product_id}.")


def cmd_product_recommend_subreddits(args):
    try:
        profile = load(args.product_id)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        suggestions = recommend_subreddits(profile, limit=args.limit)
    except WriterConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\nSuggested subreddits for '{profile['name']}':")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. r/{s['name']} — {s['why']}")

    confirm = input("\nAdd all to profile? [y/N]: ").strip().lower()
    if confirm == "y":
        for s in suggestions:
            profile.setdefault("subreddits", []).append({"name": s["name"], "why": s["why"], "added_by": "ai"})
        save(profile)
        print(f"Added {len(suggestions)} subreddits.")
