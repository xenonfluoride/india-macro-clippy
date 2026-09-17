---
name: india-macro-rss-newsletter
description: Build or refresh a concise India macro and technology newsletter from RSS/Atom feeds, with source provenance, a strict recency window, editorial selection, and HTML quality checks. Use for India-focused market, policy, or technology briefs; do not use for general news digests or live-price data alone.
metadata:
  short-description: RSS-first India macro and tech newsletter
---

# India Macro RSS Newsletter

Build a short, source-linked newsletter for India macro, markets, and technology. The page should read as a useful morning brief, not an RSS reader.

## Source boundary

- Use RSS or Atom feeds to discover newsletter stories. Do not use web search to fill editorial sections unless the user explicitly changes this rule.
- Keep a timestamped audit of each fetched item, selected item, and feed failure.
- Enforce the requested recency cutoff. The default is 48 hours; discard undated items.
- Bloomberg author RSS feeds are welcome inputs. Treat a failed or restricted feed as unavailable, never as permission to substitute a search result.
- Omit PIB by default. Add it only when the user requests it.

## Editorial selection

Select fewer stories when the alternatives are weak. Prefer a mix of primary policy sources, high-quality reporting, and distinct subjects.

- Reject routine central-bank operations, stock tips, dividend alerts, listing chatter, gadget reviews, product-spec posts, and non-India tech stories.
- Require a concrete India macro, market, policy, deep-tech, payments, regulation, company, or infrastructure signal.
- Avoid repeating a source or theme unless the event genuinely needs follow-up coverage.
- Preserve the reporter's headline. You may remove publisher-style tails such as “check the details” or “experts explain.”
- Give every selected item a two-sentence **Why it matters** note. Sentence one states the exposure, incentive, or mechanism. Sentence two names the next observable signal, tradeoff, or decision point. Do not reuse the same note for two different stories.

## Page shape

Keep the established order: Market Tape and chart, Macro, India Tech, then Tomorrow’s catalysts. The catalyst section should appear once, at the end. Keep market prices separate from RSS news, and label any non-RSS price source.

Use source links and publication times. Keep a short source label in every card. Avoid filler such as “Open the source for the full report.”

## Evaluate before delivery

Run `scripts/evaluate_newsletter.py` against the generated HTML and RSS audit. Read [references/evaluation-rubric.md](references/evaluation-rubric.md) if the evaluator reports a failure or warning. Fix failed checks before delivery; report any unavailable feeds without inventing replacements.
