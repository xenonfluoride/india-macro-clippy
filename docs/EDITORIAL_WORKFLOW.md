# Editorial workflow and artifact contract

## Run lifecycle

`capture → review → compose → semantic check → render/validate → promote → commit/push → verify deployment`

Capture and Market Tape never touch published outputs. Raw evidence and capture files are created exclusively and cannot be overwritten by these commands. Editorial files can be revised by the editor, but revisions invalidate their verification hashes. Failed runs remain on disk.

`work/build_newsletter.py --hours 36` prints an absolute RUN directory. Use that exact path with subsequent commands. `--replay FILE` imports a saved evidence batch for diagnosis and marks it replay; promotion always rejects it.

The accepted site is an immutable directory under `outputs/editions/`. `outputs/current.json` identifies it and hashes its manifest. Only replacing this single pointer changes the authoritative edition. Root-level legacy outputs remain the historical site and are not v2 working files.

## Capture and history

`capture.json` stores schema_version=2, run_id, mode, captured_at, cutoff, hours, feeds and candidates. Every candidate has id, source, section (feed suggestion), title, summary, link and published_at. ID hashes all original evidence fields except suggested section. Do not edit any original field.

Raw RSS files are under `raw/`. Live validation reparses them and checks the complete candidate pool, not just selected items. Feed statuses include attempts, exceptions, parser drops and old/future/fresh/exact-duplicate counts. Only exact identical evidence records are collapsed; different source coverage remains available for editorial clustering.

`history.json` snapshots the accepted publication ledger. On migration it is seeded from the last legacy edition. Older editions remain in Git and should be considered manually when relevant; the initial seed does not pretend to reconstruct all historical events. Promotion checks that history has not changed while the edition was being prepared.

## Review every candidate

Use `python3 -B work/newsletter.py context --run RUN --offset 0 --limit 40`, then follow next_offset. Never skip rejected-looking records before reading their evidence. Retain excerpts as text, not assertions that an article body was consulted.

`review.json`:

```json
{
  "schema_version": 2,
  "run_id": "same-as-capture",
  "editor": "actual reviewing session or person",
  "capture_sha256": "sha256 of capture.json bytes",
  "candidates": [
    {
      "id": "original candidate id",
      "event": "Discrete event or bounded attributed claim",
      "actor": "Actor established in the RSS",
      "action_type": "Completed action, commitment, proposal, estimate, commentary or other precise description",
      "india_exposure": "Concrete Indian constituency or absence of support",
      "mechanism": "Case-specific exposure or why no editorial mechanism is established",
      "evidence": ["Exact nonempty substrings of the RSS title or summary"],
      "confidence": "high",
      "materiality": 4,
      "lane": "macro",
      "decision": "select",
      "event_key": "stable-actor-action-object-date",
      "reason": "Why this disposition follows from evidence and edition priorities"
    }
  ]
}
```

Confidence is high/medium/low; materiality is 0–5 and separate from confidence. Lanes are macro/national/tech/out-of-scope. Decisions are select/update/eligible/reject/duplicate. A duplicate needs duplicate_of pointing to a non-duplicate reviewed representative with the same event_key. An update needs previous_event_key present in history and a specific new_evidence statement. Source and theme diversity influence judgment but are not automatic rejection rules.

No hardcoded list excludes words, people, sources or companies. Named forecasts, surveys and reports can be substantive. Evaluate their methods/limitations only to the extent the RSS actually establishes them; never call an estimate an audited result. Distinguish an old event newly reported from a decision made today.

## Edition data

`edition.json` has schema_version, run_id, created_at (timezone-aware ISO), date (IST calendar date), positive issue integer, hero, hero_card_ids, cards, catalysts and catalyst_review.

Each card has:

- id and lane matching its selected review;
- headline exactly preserving the RSS title;
- brief consisting of complete, attributed factual sentences;
- mechanism: one complete sentence explaining the exposure;
- watch: a distinct complete sentence naming the next observable signal or tradeoff;
- claims: statement/evidence records covering the brief in order. Joining all statement values with spaces must reproduce the entire brief; each evidence value must occur exactly in that candidate's RSS title/summary.

Mechanism and watch are analysis fields. Do not hide additional news claims or unestablished numbers in them. The prose-shape check is deliberately conservative; avoid sentence fragments, ellipses and ambiguous abbreviations.

hero_card_ids must cover all selected cards. Each catalyst requires id, date (tomorrow in IST), text and a supporting exact evidence substring. Its candidate cannot also be a selected card. The editor verifies the date is actually supported by the quoted source, not simply entered into JSON. When none qualifies, use an empty catalysts array and a case-specific catalyst_review explanation.

`market.json` is produced only by the separate updater. Its raw provider response and per-symbol timestamp/value checks are required. A 96-hour ceiling accommodates an ordinary weekend but may hold publication over a longer holiday; do not silently relax it. Daily bars are not guaranteed completed-session closes.

## Semantic verification

After composing, run `python3 -B work/newsletter.py verification-context --run RUN`. It validates mechanical inputs and prints input/template hashes. It does not create an approval.

Read the final briefs and analysis against the original evidence, compare history, and inspect the hero/catalysts. Author `verification.json` with schema_version=2, verdict=approved, actual reviewer, checked_at, exact input_hashes and template_sha256. Include:

- candidate_coverage: evidence that the full pool and alternatives were reviewed;
- hero and catalysts: specific verification findings;
- cards: exactly one record per card, with id, factual_support, analysis and novelty findings of at least 35 characters each.

This may be a second pass in the same model session. Do not claim independence or an external reviewer. The checks are an accountable editorial record, not a machine proof of truth. Never copy generic approval language, regenerate hashes to bless changed content without rereading it, or call the unit-test fixture approver in production.

## Render and publish

Run:

```sh
python3 -B work/newsletter.py render --run RUN
python3 -B -m unittest work/test_build_newsletter.py
python3 -B skill/india-macro-rss-newsletter/scripts/evaluate_newsletter.py --run RUN
```

Correct JSON and redo verification if necessary. Do not edit HTML. Rendering preserves the established layout, escapes editorial data, keeps Market Tape separate and produces one closing catalyst module.

For an authorized live publication, run `python3 -B work/newsletter.py promote --run RUN`. It checks current evidence freshness, all hashes, history and prices; stages and validates an immutable bundle; then atomically replaces the accepted pointer. An interrupt before the pointer swap leaves the existing edition authoritative. A process crash can leave a lock or an unreferenced bundle: inspect it before recovery and never delete the current accepted directory.

Stage only `outputs/current.json`, the returned complete edition directory, and intentional implementation/documentation files. Run checks on the staged change, commit `chore: refresh newsletter`, and push. CI repeats unit tests and accepted-bundle checks and publishes through `work/assemble_site.py`. Verify Pages success and the visible run ID before reporting publication.

No pointer exists until first v2 acceptance. During migration, CI tests the code and skips deployment, preserving the legacy site. An invalid pointer/bundle fails CI instead of falling back to unverified content.

`--historical` permits a reproducible archived check; it never enables promotion. Shadow editions are demonstrations, not publications. Failed runs and their diagnostics should be retained locally, with only deliberate representative fixtures committed.

## Current demonstration

`work/runs/20261012T075140Z-b5180c1a/` replays the audit's fixed 249-candidate batch. The case-by-case editorial decisions are in `work/audits/2026-10-12/shadow-decisions.tsv`; `assemble_shadow.py` merely packages those authored decisions and seven briefs. It is not part of the scheduled selection code and cannot generalize to another batch. A separate actual Yahoo snapshot and explicitly authored verification complete the demonstration.

Before unattended publishing, inspect the shadow page and retain these regression tests. Future shadow runs should use genuinely new evidence and fresh editorial assessments, never recycled approvals.
