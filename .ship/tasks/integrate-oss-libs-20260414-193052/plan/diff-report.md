# Diff Report: Host vs Peer Spec

WARNING: Peer spec was self-generated, not independent.

---

## D1: PRAW author=None serialization

**Host:** No handling of deleted-author submissions
**Peer:** `str(sub.author) if sub.author else "[deleted]"` required

**Resolution: concede to peer**
Code evidence: `content.py:_normalise_post()` requires `author` key as string. PRAW docs confirm `submission.author` is `None` for deleted accounts. Without handling, `str(None)` would yield `"None"` which is misleading.

**Action:** PRAWClient serializer must use `str(sub.author) if sub.author else "[deleted]"`.

---

## D2: rich Console non-TTY auto-detection

**Host:** Tests need "update assertions to match new format strings" (vague)
**Peer:** `Console(file=StringIO())` auto-detects non-TTY, renders plain text; same string assertions still work

**Resolution: concede to peer — with partial correction**
Code evidence: rich `Console(file=f)` when `f` is not a TTY sets `no_color=True` and renders without ANSI. Table content strings like `"python"`, `"1,468,454"` will appear in output. However, column borders (`│`) will still be present. Assertions checking exact line formats will need updating; assertions checking string containment (which is what `test_display.py` uses) will survive.

**Action:** test_display.py: replace `patch("sys.stdout", buf)` with `console=Console(file=buf, force_terminal=False)` injection. Keep string-containment assertions.

---

## D3: newspaper import name

**Host:** references `newspaper3k` package
**Peer:** Python import is `import newspaper`

**Resolution: concede to peer**
Code evidence: confirmed — PyPI package is `newspaper3k` but `import newspaper` is the correct Python import. `extractor.py` must use `import newspaper`.

---

## D4: schedule daemon load_profile import

**Host:** implied `load_profile` needs to be imported
**Peer:** `load` already imported as `load_profile` alias at `cli_scan.py:7`

**Resolution: concede to peer**
Code evidence: `cli_scan.py:7` — `from .profile_store import load, ProfileNotFoundError`. No new import needed — `cmd_scan_daemon` calls `load(args.product)` same as `cmd_scan_run:13`.

---

## D5: PRAW user_agent

**Host:** Not addressed
**Peer:** PRAW requires non-empty `user_agent`

**Resolution: concede to peer**
Code evidence: PRAW raises `praw.exceptions.MissingRequiredAttributeException` if `user_agent` is empty. Use env `REDDIT_USER_AGENT` with fallback `"reddit-toolkit/1.0"`.

---

## D6: newspaper3k vs newspaper4k

**Host:** `newspaper3k` in pyproject.toml
**Peer:** Python 3.12+ compatibility issues; use `newspaper4k`

**Resolution: patched — use newspaper4k**
Code evidence: `pyproject.toml:9` — `requires-python = ">=3.10"`. newspaper3k is unmaintained since 2021 and has lxml/Python 3.12 incompatibilities. newspaper4k is the active maintained fork with same `import newspaper` API. Since the project targets Python 3.10+ (including 3.12), newspaper4k is the safer choice.

**Action:** pyproject.toml dependency `"newspaper4k>=0.9.3"` instead of `"newspaper3k"`.

---

## Final Dispositions

| ID | Item | Disposition |
|----|------|-------------|
| D1 | PRAW author=None | conceded — peer correct |
| D2 | rich test assertion style | conceded — string containment survives |
| D3 | newspaper import name | conceded — peer correct |
| D4 | load_profile already imported | conceded — peer correct |
| D5 | PRAW user_agent | conceded — peer correct |
| D6 | newspaper3k vs newspaper4k | patched — use newspaper4k |

No escalated items.
