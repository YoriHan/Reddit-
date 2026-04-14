import sys

from .profile_store import load, ProfileNotFoundError
from .notion_pusher import ensure_database, link_database, NotionConfigError


def cmd_notion_setup(args):
    try:
        profile = load(args.product)
    except ProfileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        if args.database_id:
            link_database(profile["id"], args.database_id)
            db_id = args.database_id
            print(f"Linked existing database: {db_id}")
        else:
            db_id = ensure_database(profile["id"], profile)
            print(f"Notion database ready: {db_id}")
    except NotionConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Open in Notion: https://notion.so/{db_id.replace('-', '')}")
