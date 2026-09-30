# Project instructions

## Documentation is required

Always update documentation in the same change when modifying the RSS roster, editorial selection rules, newsletter structure, market-data workflow, evaluator, validation commands, or publishing process. At minimum, keep `README.md`, `skill/india-macro-rss-newsletter/SKILL.md`, and `skill/india-macro-rss-newsletter/references/evaluation-rubric.md` accurate. Record durable sourcing and quality decisions in `docs/EDITORIAL_DECISIONS.md`.

## Publishing guardrails

- Editorial cards must be grounded only in the RSS audit. Do not use web search to fill stories or catalysts.
- The editorial recency window is 36 hours. The builder and evaluator reject a longer window so consecutive daily issues cannot silently drift back to two-day coverage.
- Market Tape is a clearly labelled Yahoo Finance price snapshot, not editorial inference. Do not publish a routine daily chart without a distinct analytical purpose.
- Preserve the last good site if RSS selection, market data, tests, or evaluation fail.
- Publish only after `python3 -m unittest work/test_build_newsletter.py` and the newsletter evaluator pass.
- The builder must reject IPO/listing chatter, market-mover posts, standalone currency and index recaps, recycled long-range growth forecasts, speculative meeting previews, reported ministerial discussions without a decision, investor punditry, generic placement announcements, offshore capex without an India operating effect, macro ministerial or executive commentary, thin market-calendar items, party-political churn, unsupported spokesperson claims, and generic tech fundraising, startup-support, conference-preview, workforce-gap, ministerial, or executive commentary. It should leave a lane short rather than fill it with a weak item. India Tech includes concrete domestic digital-policy decisions, rejects offshore incidents that only speculate about a possible India response, prefers disclosed operating acquisitions over generic workforce reports when they compete for a source slot, avoids duplicate cards for one event, and refreshes the visible edition date on a new issue.
- Macro relevance must use word-aware themes, not raw substring checks. Keep the candidate-level score, detected themes, and final inclusion or exclusion reason in the RSS audit so editorial misses can be inspected.
- National & Strategy reads Hindustan Times India, NDTV India, and BBC News India every build. It may publish up to three distinct high-signal events, with independent source corroboration used as a ranking boost and duplicate events collapsed to one card.
