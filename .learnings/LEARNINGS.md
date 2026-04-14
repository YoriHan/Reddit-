# Project Learnings

This file is auto-managed by `/ship:learn`. Verified entries are rules.
Pending entries are fresh observations awaiting validation.

---

## [LRN-20260411-001] pitfall

**Logged**: 2026-04-11T00:00:00Z
**Priority**: high
**Status**: verified
**Area**: infra

### Summary
The `/ship:auto` pipeline will block at the handoff (PR creation) step if the local repo has no GitHub remote configured.

### Details
The pipeline ran successfully through branch creation and commits, but was unable to push or open a pull request because no `origin` remote pointing to GitHub exists. The repo at `/Users/yorihan/Reddit小工具` is local-only with no remotes (`git remote -v` returns empty). `/ship:auto` has no fallback for this case — it simply blocks at the handoff stage.

### Suggested Action
Before running `/ship:auto` on a project, verify a GitHub remote exists with `git remote -v`. If missing, create the remote repo on GitHub first (e.g., `gh repo create`) and add it with `git remote add origin <url>`. Only then invoke the pipeline.

### Metadata
- Source: auto_detected
- Related Files: /Users/yorihan/Reddit小工具/.git/config
- Tags: git, remote, github, pipeline, ship:auto, handoff, pr

---
