---
name: india-macro-rss-newsletter
description: Capture, review, compose, validate and publish an RSS-only India macro, strategy and technology newsletter with complete candidate review and immutable evidence.
---

# India Macro RSS Newsletter — v2

Read this file and `references/evaluation-rubric.md` completely before an edition. Artifact schemas and examples are in `docs/EDITORIAL_WORKFLOW.md`.

## Evidence capture

1. Synchronize the requested branch using `git pull --ff-only`. Preserve changes on failure. A restricted-network DNS failure needs an approved network retry, not an assumption that GitHub is unavailable.
2. Run `python3 -B work/build_newsletter.py --hours 36`. Record the printed RUN directory. This captures evidence only; it produces no selection or review.
3. Run `python3 -B work/update_market_tape.py --run RUN`. Any price failure blocks publication. Diagnostics stay in the run.
4. Read `capture.json`, feed failures and `history.json`. Inspect all candidates using `python3 -B work/newsletter.py context --run RUN --offset 0 --limit 40`; follow every next_offset. Do not dump a whole batch and then treat truncated output as a full review.

The roster in `work/feeds.py` contains Business Standard Economy & Policy, Business Standard Companies, Economic Times Economy, The Hindu Economy, Mint Markets, Mint Companies, Mongabay India, Hindustan Times India, NDTV India, BBC News India, Economic Times Tech, The Hindu Technology, Mint Technology, YourStory and Inc42. Read all configured inputs. Feed category does not fix the editorial lane.

Use original titles, RSS summaries, URLs, sources and publication timestamps only. Never use web search or article bodies to fill missing facts. Raw responses and parser/drop counts are retained. Future-dated and undated records are excluded; updated-only entries cannot silently become new publications.

## Complete editorial review

Author `review.json` yourself for every candidate ID. Python must not choose stories or synthesize a review. Record event, actor, action_type, india_exposure, mechanism, evidence spans, confidence, materiality, lane, decision and reason. An actor not established by the evidence must be explicitly marked uncertain with a case-specific explanation; never invent one.

Confidence means support for a bounded claim, separate from importance. Estimates, proposals and company statements can be useful if labelled accurately. A report or an executive quote is not automatically commentary. Reject actual stock advice, alerts, routine recaps, consumer reviews, local crime, political churn, unrelated global stories, unsupported commentary and duplicate events. Do not use a phrase blacklist.

Use decisions select, update, eligible, reject or duplicate. Source/theme diversity are soft preferences. Choose five to seven high-confidence distinct events across the three lanes when supported. No fixed Macro cap. If fewer than five survive a complete review, retain the failed run and hold publication.

Give each selected event a stable descriptive event_key. Duplicate records reference a non-duplicate representative via duplicate_of and share its event key; retain their evidence. Review history before selection. An update to a published event needs previous_event_key and a specific new_evidence explanation, not merely a new source URL.

## Composition and semantic verification

Author `edition.json`: issue/date/created_at, cards, hero/hero_card_ids, catalysts and catalyst_review. Preserve RSS headlines. Each brief has claims whose statement strings cover the whole brief and whose evidence strings appear exactly in the source. Do not smuggle new numbers, dates, named entities or completed-action claims into a paraphrase.

Write each card's mechanism and watch as separate, distinct single sentences. They are analysis and a next observable signal, not additional unsupported news. Write the hero from the selected slate. Inspect tomorrow's date-specific items and record why none qualify when appropriate. A stock record-date or conference preview is not a useful catalyst merely because it has a date.

Get hashes with `python3 -B work/newsletter.py verification-context --run RUN`. Conduct a separate evidence-check pass on every final card, its attribution/action status, analysis, novelty, hero and catalysts. Author `verification.json` with specific findings and the exact hashes; the context command does not approve the edition. This can be a second pass by the current session; do not claim an independent reviewer unless one actually reviewed it. Edits after verification require another check and updated verification.

## Render, validate, publish

- `python3 -B work/newsletter.py render --run RUN`
- `python3 -B -m unittest work/test_build_newsletter.py`
- `python3 -B skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py --run RUN`

Fix source artifacts, not HTML. Layout stays Market Tape, Macro, National & Strategy, India Tech, then exactly one Tomorrow’s catalysts module. Hero and visible issue date are refreshed. Market Tape is labelled Yahoo Finance daily-bar price snapshots with each instrument's observation time; it is not RSS-derived and does not promise a completed session close.

Only when publishing is authorized and all checks pass, run `python3 -B work/newsletter.py promote --run RUN`. Stage the returned `outputs/editions/RUN_ID/` and `outputs/current.json`, plus only intentional pipeline/documentation changes. Commit `chore: refresh newsletter`, then push. Verify Pages completion and the deployed run ID. A successful push alone is not deployment confirmation.

Never restore away evidence or overwrite the legacy three output files. No accepted pointer means the last legacy site stays live. A failed run or price fetch means no push. Preserve failed run directories. Replay/shadow captures cannot be promoted even if they pass historical validation.

Changes to the pipeline require the documentation updates specified in CLAUDE.md. Do not add edition-specific prose or facts to Python.
