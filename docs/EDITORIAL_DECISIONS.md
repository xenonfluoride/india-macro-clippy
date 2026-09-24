# Editorial decisions

This log records durable choices behind the newsletter so later editions do not reopen settled quality and sourcing questions.

## 2026-09-22: Use a 10-feed, India-focused RSS roster

The roster was chosen after a live 48-hour audit of source volume, recency, and whether RSS summaries contained enough detail for an editor-written card.

- **Macro:** Business Standard Economy & Policy, Business Standard Companies, Economic Times Economy, The Hindu Economy, and Mint Markets provide recurring economic, trade, external-balance, and market-policy coverage.
- **National & Strategy:** The Hindu National is the sole input. It is filtered for policy, law, security, and foreign affairs rather than treated as a general national-news feed.
- **India Tech:** Economic Times Tech, The Hindu Technology, YourStory, and Inc42 provide a mix of infrastructure, regulation, funding, and builders.
- **Removed sources:** Bloomberg author feeds, RBI, SEBI, Indian Express economy, markets, and technology feeds, Mint Technology, and MediaNama did not consistently produce enough usable RSS detail or volume for this daily brief.
- **Rejected trial:** The Print India was tested but not retained because its current feed skewed toward regional and local news rather than the national-strategy beat.
- **Reuters:** Reuters India is not included. Reuters RSS distribution is authenticated through Reuters Connect, and no reliable public India RSS endpoint is used.

## 2026-09-22: Make selection quality explicit

- Keep a hard 48-hour editorial window and retain a JSON audit of source items, selected cards, and fetch failures.
- Do not use web search to write editorial cards or catalysts. Market Tape and the chart are separately sourced from Yahoo Finance.
- Reject routine central-bank operations, stock tips, dividends, listing chatter, gadget reviews, product-spec posts, generic local-national stories, and unrelated global technology.
- Prevent repeated Macro themes in one issue across energy, external finance, trade, monetary policy, and markets.
- Give National & Strategy one high-signal card rather than padding it with local incidents or live-news churn.
- Require a story-specific, two-sentence `Why it matters`: mechanism first, then the next observable signal, tradeoff, or decision point.

## 2026-09-22: Publish only after all gates pass

Each issue must have a publishable RSS selection, a successful separate market-data update, passing unit tests, and a passing newsletter evaluator. If a gate fails, preserve the last good site and do not push.

## 2026-09-24: Make automated selection reject weak recaps and local political churn

- Draft-IPO/listing coverage and repeated agency growth-forecast recaps are not editorial cards: they either duplicate a broad macro signal or invite price-focused treatment without a concrete economy-wide mechanism.
- Macro diversity now explicitly distinguishes food prices, credit allocation, and digital payments alongside energy, external finance, trade, monetary policy, and markets.
- National & Strategy prioritises foreign-affairs, security, legal, and policy consequences over state-political personalities or event churn.
- The builder updates the page title and visible issue date once per new calendar edition; catalysts must be updated to the following day and remain the sole closing module.
