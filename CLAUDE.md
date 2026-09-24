# Project instructions

## Documentation is required

Always update documentation in the same change when modifying the RSS roster, editorial selection rules, newsletter structure, market-data workflow, evaluator, validation commands, or publishing process. At minimum, keep `README.md`, `skill/india-macro-rss-newsletter/SKILL.md`, and `skill/india-macro-rss-newsletter/references/evaluation-rubric.md` accurate. Record durable sourcing and quality decisions in `docs/EDITORIAL_DECISIONS.md`.

## Publishing guardrails

- Editorial cards must be grounded only in the RSS audit. Do not use web search to fill stories or catalysts.
- Market Tape is a clearly labelled Yahoo Finance price snapshot, not editorial inference. Do not publish a routine daily chart without a distinct analytical purpose.
- Preserve the last good site if RSS selection, market data, tests, or evaluation fail.
- Publish only after `python3 -m unittest work/test_build_newsletter.py` and the newsletter evaluator pass.
- The builder must reject IPO/listing chatter, recycled growth-forecast roundups, and state-politics churn; it must also refresh the visible edition date on a new issue.
