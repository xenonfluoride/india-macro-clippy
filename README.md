# India Macro Clippy

India Macro Clippy is a static, source-linked daily briefing for India macro, national strategy, and technology. GitHub Pages publishes the site from `main`.

## Editorial boundary

Editorial cards use only the configured RSS/Atom feeds and their title and summary text. Market Tape is a clearly labelled Yahoo Finance price snapshot from a separate updater. Do not use web search to fill a story, price, or catalyst.

The builder keeps a hard 36-hour window, records every retained item and fetch failure in `outputs/india-macro-clippy-data.json`, and publishes only source-linked cards that pass the relevance filters.

## Current RSS roster

| Beat | Sources |
| --- | --- |
| Macro | Business Standard Economy & Policy; Business Standard Companies; Economic Times Economy; The Hindu Economy; Mint Markets |
| National & Strategy | Hindustan Times India; NDTV India; BBC News India |
| India Tech | Economic Times Tech; The Hindu Technology; YourStory; Inc42 |

The macro selector uses word-aware editorial themes rather than raw substring matching. It covers food and rural conditions, energy and infrastructure, climate and water, external finance, trade and rules, investment and industry, digital payments, monetary policy, and markets; it also prevents a theme from repeating in one issue. It excludes draft-IPO/listing chatter, market-mover posts, standalone currency and index recaps, recycled long-range market forecasts, speculative meeting previews, reported ministerial discussions without a decision, investor punditry, generic placement announcements, offshore capex by an India-linked company without an India operating effect, and ministerial or executive commentary; it leaves a slot empty rather than use a thin market-calendar item. The audit includes each candidate’s score, themes, and selection decision. National & Strategy reads three independent feeds on every build, admits India-relevant policy, law, security, and foreign-affairs stories, and rejects local incidents, live updates, price checks, entertainment, party-political churn, and unsupported spokesperson claims. Independent corroboration raises an item’s rank but never creates a duplicate card; the lane can carry up to three distinct high-signal events. India Tech also excludes IPO trackers, routine fund-raise announcements, generic startup-support, conference-preview, and workforce-gap reports, generic ministerial or executive commentary, and offshore incidents that merely invite hypothetical India action; every card needs a concrete Indian operating, regulatory, or infrastructure signal, and one event receives only one card. A disclosed India-company acquisition receives an explicit relevance boost because it is a concrete operating decision.

## Build and publish

```bash
git pull --ff-only
python3 work/build_newsletter.py --hours 36
python3 work/update_market_tape.py
python3 -m unittest work/test_build_newsletter.py
python3 skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py \
  outputs/india-macro-clippy.html outputs/india-macro-clippy-data.json
```

After the builder runs, rewrite the selected cards in `outputs/india-macro-clippy.html` as concise editor-written briefs with complete sentences, never an ellipsis. Each `Why it matters` note must use two story-specific sentences: mechanism first, then the next observable signal, tradeoff, or decision point. The builder refreshes the visible edition date; keep exactly one Tomorrow’s catalysts section at the end, and leave it empty rather than recycling editorial stories when the RSS audit has no distinct, dated catalyst.

If every command passes and the issue is publishable, commit the generated HTML and audit plus intentional builder, evaluator, test, or documentation updates with `chore: refresh newsletter`, then `git push`. Do not push if RSS selection, market data, tests, or evaluation fail.

## Documentation standard

Documentation is part of every change. Any update to the RSS roster, editorial rules, pipeline, evaluator, validation commands, or publishing workflow must update this README and the relevant files in `skill/india-macro-rss-newsletter/` in the same change. Record durable sourcing and quality choices in [docs/EDITORIAL_DECISIONS.md](docs/EDITORIAL_DECISIONS.md).
