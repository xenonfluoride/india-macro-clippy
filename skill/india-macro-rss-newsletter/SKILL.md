---
name: india-macro-rss-newsletter
description: Build or refresh a concise India macro, national-strategy, and technology newsletter from RSS/Atom feeds, with source provenance, a strict recency window, editorial selection, and HTML quality checks. Use for India-focused market, policy, strategy, or technology briefs; do not use for general news digests or live-price data alone.
metadata:
  short-description: RSS-first India macro and tech newsletter
---

# India Macro RSS Newsletter

Build a short, source-linked newsletter for India macro, national strategy, markets, and technology. The page should read as a useful morning brief, not an RSS reader.

## Source boundary

- Use RSS or Atom feeds to discover newsletter stories. Do not use web search to fill editorial sections unless the user explicitly changes this rule.
- Keep a timestamped audit of each fetched item, selected item, and feed failure.
- Enforce the requested recency cutoff. The maximum and default is 36 hours; discard undated items.
- The configured roster is: Business Standard Economy & Policy, Business Standard Companies, Economic Times Economy, The Hindu Economy, Mint Markets, Hindustan Times India, NDTV India, BBC News India, Economic Times Tech, The Hindu Technology, YourStory, and Inc42.
- Treat a failed or restricted feed as unavailable, never as permission to substitute a search result.

## Editorial selection

Select fewer stories when the alternatives are weak, including thin market-calendar items. Prefer a mix of primary policy sources, high-quality reporting, and distinct subjects.

- Reject routine central-bank operations, stock tips, dividend alerts, draft-IPO/listing chatter and IPO trackers, market-mover posts, standalone currency and index recaps, recycled long-range market forecasts, speculative meeting previews, reported ministerial discussions without a decision, investor punditry, offshore capex without an India operating effect, macro ministerial or executive commentary, gadget reviews, product-spec posts, non-India tech stories or offshore incidents that only speculate about India, routine fund-raise announcements, generic startup-support, conference-preview, or workforce-gap reports, and generic ministerial or executive commentary without a concrete Indian operating, regulatory, or infrastructure signal. A concrete domestic digital-policy decision belongs in India Tech, even when the RSS summary omits the word “India”; collapse duplicate coverage of the same rule to one card. Prefer a disclosed India-company acquisition over a generic workforce report when both compete for a source slot.
- Require a concrete India macro, market, policy, deep-tech, payments, regulation, company, or infrastructure signal.
- Avoid repeating a source, theme, or event unless it genuinely needs follow-up coverage; one event should not occupy two cards simply because it appeared in more than one feed.
- Use word-aware Macro themes, rather than raw substring checks: food and rural conditions; energy and infrastructure; climate and water; external finance; trade and rules; investment and industry; digital payments; monetary policy; and markets. Keep themes distinct in one issue and retain each candidate’s score, detected themes, and selection decision in the audit. Read all three National & Strategy feeds on every build. Use that lane only for policy, law, security, or foreign-affairs stories; reject local incidents, party-political churn, live-news churn, and unsupported spokesperson claims. Treat independent coverage of the same event as corroboration: raise its rank, expose the corroborating sources in the audit, and render one card for the event. The lane may include up to three distinct high-signal events.
- Preserve the reporter's headline. You may remove publisher-style tails such as “check the details” or “experts explain.”
- Give every selected item a two-sentence **Why it matters** note. Sentence one states the exposure, incentive, or mechanism. Sentence two names the next observable signal, tradeoff, or decision point. Do not reuse the same note for two different stories. Card summaries must end on a complete sentence, never an ellipsis.

## Page shape

Keep the established order: Market Tape, Macro, National & Strategy, India Tech, then Tomorrow’s catalysts. The catalyst section should appear once, at the end. Use it only for distinct, date-specific signals in the audit; state plainly when none qualify instead of recycling editorial stories. Refresh the visible edition date for a new issue. Keep market prices separate from RSS news, label the separate price source, and omit a routine daily chart unless it adds a genuinely new comparison or analysis.

Use source links and publication times. Keep a short source label in every card. Avoid filler such as “Open the source for the full report.”

## Evaluate before delivery

Run `scripts/evaluate_newsletter.py` against the generated HTML and RSS audit. Read [references/evaluation-rubric.md](references/evaluation-rubric.md) if the evaluator reports a failure or warning. Fix failed checks before delivery; report any unavailable feeds without inventing replacements.
