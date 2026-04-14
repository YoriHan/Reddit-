# Diff Report

## Divergence 1: Two timestamps vs one `learned_at`

**Host spec:** Single `learned_at` (mirrors style_store.py:26)
**Peer spec:** Separate `rules_fetched_at` + `norms_learned_at`

**Evidence:** style_store.py:26 uses `data["learned_at"]` for both save and staleness. But official rules (rarely change, 30d TTL) and inferred norms (change with community, 7d TTL) have different refresh rates. Peer's dual-timestamp approach allows invalidating norms independently without re-fetching official rules.

**Disposition: conceded** — Peer wins. Adopt dual timestamps. The minimal cost is justified by allowing different TTLs.

---

## Divergence 2: `get_subreddit_rules()` location

**Host spec:** Standalone function in `rules_learner.py`
**Peer spec:** Method on `RedditClient` class (reddit_client.py)

**Evidence:** subreddits.py:1-5 uses standalone functions with `_client(client)` optional injection — not methods on RedditClient. content.py follows the same pattern. No existing functions are added to RedditClient. The standalone pattern is established.

**Disposition: proven-false** — Peer claim wrong. Keep standalone function in `rules_learner.py`, consistent with subreddits.py:4-5 pattern.

---

## Divergence 3: Target function in writer.py

**Host spec:** Extend `generate_mimic_post()` (writer.py:341)
**Peer spec:** Extend `write_post_body()` (writer.py:68)

**Evidence:** `write_post_body` (writer.py:68) is called by `cmd_write_body` (cli.py write subcommand) — a generic body writer. `generate_mimic_post` (writer.py:341) is called by `cmd_style_mimic` (cli_style.py:119) — the primary product-placement content pipeline. Rules enforcement is about making product posts compliant, so `generate_mimic_post` is the right target.

**Disposition: proven-false** — Peer wrong. Both functions get rules param, but `generate_mimic_post` is primary. Both patched: `generate_mimic_post` gets `rules=None` (primary) and `write_post_body` also gets `rules=None` (secondary, for `write body` CLI).

---

## Divergence 4: Inferred norms schema

**Host spec:** `{self_promo_hard_limit, what_gets_removed, safe_post_angles, link_rules, karma_or_age_gate, flair_required, optimal_post_length, posting_checklist}`
**Peer spec:** `{content_preferences, tone_guidelines, forbidden_topics, post_structure, engagement_patterns, community_values}`

**Evidence:** `generate_mimic_post` system prompt (writer.py:359-383) already injects `taboo_topics`, `self_promotion_tolerance`, `community_values`, `vocabulary_signals`. Rules should add what's NOT already there: actionable posting_checklist and what_gets_removed. Peer's schema is more descriptive; host's is more actionable for prompt injection.

**Disposition: patched** — Merge both. Final schema:
```
inferred_norms: {
  tone_guidelines,       # peer - descriptive
  community_values,      # peer - already used in writer.py:369
  what_gets_removed,     # host - actionable
  posting_checklist,     # host - most directly injectable into prompt
  safe_post_angles,      # host - actionable
  link_rules             # host - specific
}
```

---

## Divergence 5: Token cost tracking

**Host spec:** Not tracked
**Peer spec:** `inference_metadata.inference_token_cost`

**Evidence:** No token tracking exists anywhere in the codebase. Minor addition, no conflicts.

**Disposition: patched** — Add `inference_metadata` to schema. Low cost, useful for users.

---

## Divergence 6: Schema validation vs fallback

**Host spec:** JSON parse error → return fallback dict silently
**Peer spec:** JSON parse error → raise `NormsInferenceError` with helpful message

**Evidence:** `analyze_subreddit_style` (writer.py:324-338) uses silent fallback. But for rules, a failed inference means content might violate community rules — silent failure is dangerous. Peer's strict approach is safer here.

**Disposition: patched** — Use strict validation. Raise `RulesInferenceError` on parse fail. This is different from style analysis (where fallback is acceptable) because rules violations have real consequences.

---

## Final resolution: Zero escalated items
