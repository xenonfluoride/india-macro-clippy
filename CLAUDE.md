# Project instructions

## Source of truth

Use the v2 workflow in `skill/india-macro-rss-newsletter/SKILL.md`, its evaluation rubric, and `docs/EDITORIAL_WORKFLOW.md`. The historical blacklist and hardcoded prose in audit snapshots are evidence of defects, not reusable rules.

## Required editorial behavior

- Use only captured RSS titles and summaries for editorial facts; no search or article-body supplementation.
- Read every fresh candidate in bounded batches. Author real event, actor, action, India exposure, mechanism, confidence and disposition assessments.
- Distinguish completed actions, commitments, proposals, estimates and commentary. Confidence measures evidence support, not whether a candidate was selected.
- Feed lane, source and theme are soft guidance. Reassign lanes by substance and select five to seven cards globally.
- Reject actual stock tips, listing/dividend alerts, routine recaps, consumer reviews, local crime, political churn, unrelated global news, unsupported commentary and duplicate events. A keyword alone is never a reason.
- Keep original headlines and exact evidence. Every brief must map fully to supporting RSS spans; every Why note has one mechanism sentence and one next-signal sentence.
- Review prior publication history. New coverage of an unchanged event is not a new event; document any substantive update.
- Author the hero and inspect all dated catalyst candidates. One closing catalyst section only.

## Publication safety

Capture, Market Tape and rendering only write run directories. They must never edit the legacy output files. Failed evidence is retained.

The sole deployment pointer is `outputs/current.json`, referencing a complete immutable v2 bundle. Promotion requires live evidence, a complete model-authored review, valid prices, exact rendered HTML, explicit semantic verification bound to all input hashes, and current publication history. Never bypass the gate, fabricate approval notes, relabel a replay as live, or hand-edit HTML to hide invalid data.

Run `python3 -B -m unittest work/test_build_newsletter.py` and the evaluator with `--run RUN` before promotion. CI repeats checks. Verify the deployed edition after a push.

A validation pass does not prove semantic truth; it proves the artifacts match the explicitly reviewed version and satisfy the mechanical contract. Do not report a review as complete merely because a JSON row exists.

## Documentation

Changes to roster, editorial contracts, schema, validation or deployment must update README, this file, the skill, rubric and applicable decisions. Preserve pre-existing user changes; stage intentional paths explicitly.
