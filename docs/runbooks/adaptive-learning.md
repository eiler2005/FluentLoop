# Adaptive B2 → strong B2 → introductory C1

The product contract is [EPIC-27](../features/EPIC-27-adaptive-topic-progression.md)
and the evidence/maintenance decision is [ADR-0014](../adr/0014-adaptive-topic-progression.md).
The learner uses `/study`, `/progress`, and `/plan`; the primary keyboard stays
**Учиться · Прогресс · Ещё**. The stages describe this curriculum's evidence,
not a CEFR certificate or a claim about speaking/listening proficiency.

## Publish and activate the owner pilot

1. Run `uv run python scripts/import_adaptive_curriculum.py` for validation and
   counts without changing the database. The pack has 270 reviewed questions,
   ten topics, three stages, six practice and three transfer questions per stage.
2. Run the standard test/style/secret gates from [testing](../testing.md).
3. Take a consistent SQLite backup using `scripts/backup_sqlite.py` before
   changing the deployed database. Use the [deployment runbook](deploy.md) for
   release and container verification.
4. Apply `uv run python scripts/import_adaptive_curriculum.py --apply --subscribe-pilot`.
   The script selects the admitted owner from configuration, publishes templates,
   clones personal plans, and enables adaptive bank maintenance for that pilot.
   Reapplication must create zero additional items/plans. No real identifier is
   needed in a command or fixture. Check the importer help for mode activation.
5. Run `/plan`, then `/study`. The initial path starts with B2 evidence; the
   profile's existing `level` label alone cannot unlock introductory C1.

Keep the 86-question legacy pack and existing progress. The new bank is additive.
Only the adaptive selector can expose its questions; generic lesson/card pools
exclude them, so a transfer question remains fresh until its assessment.

## Evidence and recovery

Within a topic/stage, five distinct successful practice variants, at least 80%
accuracy over the latest ten practice responses, and two local dates spanning
24 hours prepare transfer. Fresh transfer opens at least 24 hours after readiness.
B2 needs one transfer success; strong B2 and introductory C1 need two plus a
genuine independently checked original written response. Every topic must reach
strong B2 to open introductory C1. Skipping writing is allowed, and `/progress`
then names writing as the remaining evidence. Two failures on different variants
within 14 days reset the affected topic stage into repair, including its higher
stages. Other topics keep their progress.

Familiar repetition does not unlock a level. An abandoned displayed transfer is
no longer unseen. The saved unanswered question still resumes normally, with its
original eligibility snapshot. Duplicate callbacks and foreign-user callbacks
cannot add evidence. A reported/quarantined question stops contributing evidence;
the original attempt remains stored.

## Automatic bank maintenance

`adaptive_question_bank` checks hourly at minute 17. It runs only for simple
profiles explicitly opted in through `learning.adaptive_auto_expand`. It sends no
messages. It creates variants of already approved curated targets when the
current-stage fresh pool is low, a learner reports a question, or a question has
at least three failures in its latest five attempts. Failures alone are a review
signal, not proof of a bad question.

The local-day claim is committed before network work, which takes place outside
DB transactions. Limits are two candidates/profile/day, 12 extra variants/item,
120 extra variants/profile. Restart or concurrent workers cannot renew the daily
budget. Failed or unavailable generation uses the same budget and retries on a
later local day. Without a configured Qwen/DeepSeek provider the reviewed static
pack remains usable.

The generator uses the configured fast model. A separate planner-model call
solves the question without its key, checks uniqueness, level, approved target,
explanation and novelty. Local validation additionally checks structure, English
questions, Russian feedback, key range, duplicate choices and near-duplicate
contexts. Only accepted candidates become selectable; rejection is recorded as
aggregate status on the item. Original content and history are never overwritten.
Reviewed legacy questions can gain replacement variants, but those variants
cannot manufacture adaptive mastery. Private uploaded-card content and raw user
answers are excluded from this maintenance payload.

Inspect counts with `uv run python scripts/maintain_question_bank.py`. Execute
the same bounded job with `--apply`; it cannot bypass that day's claim. Provider
usage is tracked through the existing usage log, with separate `question_variant`
and `question_review` task names. Model review reduces ambiguity but still needs
the learner's issue-report mechanism: it is not infallible human validation.

## Rollback and smoke

Run `uv run python scripts/maintain_question_bank.py --apply --disable-pilot`
to stop generation; this changes `learning.adaptive_auto_expand` without altering
attempts or curated content. Reapplying the owner subscription enables it again.
Switch the pilot to full mode through
`/settings` to stop the simple flow. Code rollback must use a pre-release database
backup if the old version cannot recognize adaptive metadata: otherwise old
selectors could expose reserved questions. Preserve current DB and backups before
such a rollback.

Smoke checks: resume the same question; answer once; repeat the old callback;
stop; open `/progress` and `/plan`; report an answered question twice; verify
quarantine and no double evidence; verify another profile is unchanged. Do not
submit invented learner answers to the live database. Automated tests exercise
the multi-day B2 progression, all-topic C1 gate, generation failure/concurrency,
and production authenticity in isolated databases.
