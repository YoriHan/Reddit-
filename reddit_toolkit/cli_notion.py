import sys

from .profile_store import load, ProfileNotFoundError
from .notion_pusher import ensure_database, NotionConfigError


def cmd_notion_setup(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        db_id = ensure_database(profile["id"], profile)
    except NotionConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Notion database ready: {db_id}")
    print(f"Open in Notion: https://notion.so/{db_id.replace('-', '')}")
