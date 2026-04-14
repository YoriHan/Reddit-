---
active: true
task_id: reddit-toolkit-discover-content-subreddits-write-posts
session_id: unknown
branch: ship/reddit-toolkit-discover-content-subreddits-write-posts
base_branch: main
phase: handoff
review_fix_round: 1
qa_fix_round: 0
started_at: "2026-04-11T00:00:00Z"
---

Build a Reddit toolkit in /Users/yorihan/Reddit小工具 that helps users:
1. Discover good Reddit content (trending posts, top posts by subreddit, search)
2. Discover good subreddits (recommendations, search, explore by topic)
3. Write Reddit content (post title generator, body writer, comment helper)

This is a greenfield project. Use Python with a simple CLI interface. Use Reddit's public JSON API (no auth required for read-only, append .json to Reddit URLs) for content discovery. For writing assistance, use the Anthropic Claude API. Create a well-structured project in /Users/yorihan/Reddit小工具.
