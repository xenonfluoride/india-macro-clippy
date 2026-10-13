# India Macro Clippy

A daily India macro, national-strategy and technology briefing. Editorial facts come only from configured RSS titles and summaries. Yahoo Finance supplies a separate Market Tape.

## Pipeline v2

The 12 October audit found false exclusions, canned historical facts and ineffective gates. The replacement separates evidence capture, editorial judgment, rendering and publication.

1. Capture immutable evidence: `python3 -B work/build_newsletter.py --hours 36`.
2. Use the printed `RUN` directory throughout. Fetch prices: `python3 -B work/update_market_tape.py --run RUN`.
3. Read candidates in batches: `python3 -B work/newsletter.py context --run RUN --offset 0 --limit 40`. Follow `next_offset` until every record has been reviewed.
4. The current model session authors `review.json` and `edition.json` in RUN. No code chooses stories, assigns confidence or writes news prose.
5. Review the complete copy against RSS evidence; obtain digests with `python3 -B work/newsletter.py verification-context --run RUN`, then author `verification.json`. Digests bind approval to the exact inputs; the command does not approve them.
6. Render and validate: `python3 -B work/newsletter.py render --run RUN`; `python3 -B skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py --run RUN`.
7. Run `python3 -B -m unittest work/test_build_newsletter.py`. Only an explicitly verified live run can be promoted: `python3 -B work/newsletter.py promote --run RUN`.

See [the editorial workflow](docs/EDITORIAL_WORKFLOW.md) for artifact schemas, review instructions and publishing.

## Sources

| Suggested beat | Configured RSS sources |
| --- | --- |
| Macro | Business Standard Economy & Policy; Business Standard Companies; Economic Times Economy; The Hindu Economy; Mint Markets; Mint Companies; Mongabay India |
| National & Strategy | Hindustan Times India; NDTV India; BBC News India |
| India Tech | Economic Times Tech; The Hindu Technology; Mint Technology; YourStory; Inc42 |

Feed categories are suggestions. The editor can reassign an onion-price report from a national feed to Macro, or an IT-company event to Tech. Source and theme diversity are soft preferences, never vetoes. Select five to seven distinct, well-supported events globally. Do not exclude an event merely for mentioning a CEO, forecast, fund, publisher or expert.

## What is authoritative

Each capture creates `work/runs/RUN_ID/`; failed runs remain inspectable. Raw RSS, source diagnostics, original normalized text, timestamps and IDs are retained. Review covers every candidate. The edition owns all prose, including the hero and catalysts.

Promotion installs an immutable bundle in `outputs/editions/RUN_ID/` and atomically replaces `outputs/current.json`. That pointer is the sole authority for deployment. A publication ledger tracks prior events and links. An unchanged event cannot be reused; a follow-up requires documented new evidence.

The old three `outputs/india-macro-clippy*` files are retained as the legacy published edition, not v2 working files. Never restore a failed run over them or overwrite its evidence. Until the first live v2 edition is accepted and pushed, the existing site remains live.

Pages CI runs the regression suite and validates the accepted bundle before deployment. It publishes HTML, capture, review, edition, market snapshot, semantic verification and manifest. Confirm the deployed run ID after a push.

## Limits and honest guarantees

The deterministic gate checks provenance, complete review coverage, exact rendering, 5–7 cards, IST issue date, 36-hour evidence bounds, typed price values, hashes and novelty declarations. It cannot prove semantic truth. The editor must check factual support, actor/action status, attribution, analysis and novelty, and record that verification. A hash prevents changing reviewed content; it does not make an inaccurate review true.

RSS summaries may be sparse. Skip unsupported claims rather than fill them from search or article bodies. Prices carry individual observation timestamps and are labelled daily-bar snapshots, not necessarily completed-session closes. The maximum observation age is 96 hours to accommodate weekends; longer closures fail closed. Any missing price blocks publication.

A 36-hour window still overlaps successive daily runs; the ledger handles repeats. The existing weekday schedule leaves a weekend coverage gap. The rebuild does not silently change that schedule or expand the recency window.

## Replay and regression evidence

`python3 -B work/build_newsletter.py --replay work/audits/2026-10-12/fetched-records.json` creates an isolated replay. Replay runs can be validated with `--historical` but can never be promoted. Historical validation is not publication authorization.

The original failure probes and legacy implementation snapshots are retained under `work/audits/2026-10-12/`. The seven-card, fully reviewed shadow run is `work/runs/20261012T075140Z-b5180c1a/`.

Keep README, CLAUDE, the newsletter skill, rubric and editorial decisions synchronized whenever this workflow changes.
