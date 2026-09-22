# India Macro Clippy

India Macro Clippy is a static, source-linked daily briefing for India macro, national strategy, and technology. GitHub Pages publishes the site from `main`.

## Editorial boundary

Editorial cards use only the configured RSS/Atom feeds and their title and summary text. Market Tape and the chart use Yahoo Finance data through a separate updater. Do not use web search to fill a story, price, or catalyst.

The builder keeps a 48-hour window, records every retained item and fetch failure in `outputs/india-macro-clippy-data.json`, and publishes only source-linked cards that pass the relevance filters.

## Current RSS roster

| Beat | Sources |
| --- | --- |
| Macro | Business Standard Economy & Policy; Business Standard Companies; Economic Times Economy; The Hindu Economy; Mint Markets |
| National & Strategy | The Hindu National |
| India Tech | Economic Times Tech; The Hindu Technology; YourStory; Inc42 |

The macro selector prevents repeated energy, external-finance, trade, monetary-policy, and market themes in one issue. The National & Strategy lane admits India-relevant policy, law, security, and foreign-affairs stories and rejects local incidents, live updates, price checks, and entertainment.

## Build and publish

```bash
git pull --ff-only
python3 work/build_newsletter.py --hours 48
python3 work/update_market_tape.py
python3 -m unittest work/test_build_newsletter.py
python3 skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py \
  outputs/india-macro-clippy.html outputs/india-macro-clippy-data.json
```

After the builder runs, rewrite the selected cards in `outputs/india-macro-clippy.html` as concise editor-written briefs. Each `Why it matters` note must use two story-specific sentences: mechanism first, then the next observable signal, tradeoff, or decision point. Keep exactly one Tomorrow’s catalysts section at the end.

If every command passes and the issue is publishable, commit the generated HTML and audit plus intentional builder, evaluator, test, or documentation updates with `chore: refresh newsletter`, then `git push`. Do not push if RSS selection, market data, tests, or evaluation fail.

## Documentation standard

Documentation is part of every change. Any update to the RSS roster, editorial rules, pipeline, evaluator, validation commands, or publishing workflow must update this README and the relevant files in `skill/india-macro-rss-newsletter/` in the same change. Record durable sourcing and quality choices in [docs/EDITORIAL_DECISIONS.md](docs/EDITORIAL_DECISIONS.md).
