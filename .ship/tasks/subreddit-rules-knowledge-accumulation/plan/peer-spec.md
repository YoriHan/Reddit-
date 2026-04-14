# Peer Spec: Subreddit Rules & Norms Accumulation

---

## 1. Data Schema

Path: `~/.reddit-toolkit/rules/<slugified-subreddit>.rules.json`

```json
{
  "subreddit": "python",
  "rules_fetched_at": "2026-04-14T12:34:56+00:00",
  "norms_learned_at": "2026-04-14T12:34:56+00:00",
  "official_rules": [
    {"id": "1", "name": "...", "description": "...", "priority": "high"}
  ],
  "inferred_norms": {
    "content_preferences": ["..."],
    "tone_guidelines": "...",
    "forbidden_topics": ["..."],
    "post_structure": "...",
    "engagement_patterns": "...",
    "community_values": ["..."]
  },
  "inference_metadata": {
    "posts_analyzed": 250,
    "norms_model_used": "claude-opus-4-5",
    "inference_token_cost": 12450
  }
}
```

Two separate timestamps: `rules_fetched_at` (official rules) and `norms_learned_at` (AI inference).

## 2. Reddit API

Endpoint: `GET /r/{subreddit}/about/rules.json`

Response shape: `{"data": {"rules": [{"short_name", "name", "description", "priority", ...}]}}`

Peer proposes adding `get_subreddit_rules()` as a **method on RedditClient** (reddit_client.py).

## 3. AI Norm Inference

Fixed 6-key output schema:
- `content_preferences`, `tone_guidelines`, `forbidden_topics`, `post_structure`, `engagement_patterns`, `community_values`

Strict schema validation with `_validate_norms_schema()`.

## 4. Storage

- TTL: 30 days for official rules, 7 days for norms (separate check)
- `--force` flag to bypass cache

## 5. Integration Points

- `reddit_client.py`: Add `get_subreddit_rules()` method to RedditClient class
- `writer.py`: Extend `write_post_body()` (not `generate_mimic_post`) with rules param
- `cli_style.py`: Load rules in `cmd_style_mimic()`, pass to generator
- `cli_scan.py`: `rules_fetcher` callback pattern into `run_scan()`
- `cli.py`: Add `rules` subcommand group
- New files: `subreddit_rules.py`, `cli_rules.py`

## 6. CLI

Same 3 commands: `rules learn`, `rules show`, `rules list`

## Key divergences from host spec

1. **Two timestamps vs one**: Peer uses `rules_fetched_at` + `norms_learned_at` separately; host uses single `learned_at`
2. **`get_subreddit_rules()` location**: Peer adds as method on `RedditClient` class; host adds as standalone function in `rules_learner.py`
3. **Target function in writer.py**: Peer extends `write_post_body()` (line 68); host extends `generate_mimic_post()` (line 341)
4. **Inferred norms schema**: Peer uses 6-key fixed schema; host uses more flexible `posting_checklist` / `what_gets_removed` style
5. **Token cost tracking**: Peer tracks in `inference_metadata`; host does not
6. **Validation**: Peer adds strict schema validation; host uses fallback dict on parse error
