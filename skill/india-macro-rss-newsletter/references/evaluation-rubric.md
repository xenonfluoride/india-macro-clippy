# Newsletter evaluation rubric — v2

The mechanical gate is `python3 -B skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py --run RUN`. It rejects old HTML/JSON pairs as publication approval.

| Area | Required evidence |
| --- | --- |
| Capture | All roster sources have status; successful live feeds have raw responses and hashes. Candidate IDs exactly match normalized raw RSS within the window. |
| Recency | Window is at most 36 hours, cutoff matches capture, no future records. Selected evidence must still be fresh at validation/promotion. Edition date uses IST. |
| Review | Every candidate has exactly one model-authored assessment with case-specific actor, event, action, exposure, mechanism, reason, confidence and exact RSS evidence. Missing rows or old placeholder strings fail. |
| Selection | Five to seven high-confidence cards, exactly matching selected/update decisions. No keyword veto, source quota or hard theme exclusion. Event keys are distinct. |
| History | Previously published links/events require an explicit update, previous event key and new evidence. Editor checks semantic repeats across different headlines too. |
| Facts | Claims cover the entire brief and quote supporting RSS spans. Original headline is preserved. Editor verifies that the spans actually entail the claims, including numbers, dates and action status. |
| Analysis | Exactly one mechanism sentence and one distinct next-signal sentence per card; no repeated notes. Editor checks story specificity and distinguishes inference from source facts. |
| Prices | Four finite positive quotes, correct symbols/currencies, correct changes, ordered per-symbol timestamps, maximum 96-hour observation age and same-edition fetch. Values reproduce captured Yahoo payloads. Missing/failing data blocks publishing. |
| Hero/catalysts | Hero explicitly reviewed against the slate. Dated, distinct RSS-backed catalysts only; otherwise a recorded review explains the absence. |
| Verification | A separate semantic-check pass is recorded for every card and the edition, bound to hashes of capture/history/review/edition/market/template. No command generates approval. |
| Rendering | HTML must exactly equal deterministic rendering of the verified edition. Layout, attribution, dates and prose therefore cannot be hand-edited away from reviewed data. |
| Publication | Only a live run with unchanged history can advance the atomic accepted pointer. CI validates manifest, artifacts and rendering before Pages assembly. |

The gate does not prove semantic truth. A plausible but false paraphrase with matching evidence IDs still requires an honest editorial evidence check; hashes establish integrity, not truth. Never label a syntactically complete generated placeholder file an LLM review.

Historical replay checks are useful for regressions but cannot authorize publication. Keep failed captures and reviews. Warnings must be resolved or explained; failures block publication.

The earlier hard-theme, keyword-blacklist and 1–8-card behaviors are superseded by this contract. A 36-hour window does not prevent repeated events and a weekday-only schedule has an uncovered weekend interval; do not silently widen the window to compensate.
