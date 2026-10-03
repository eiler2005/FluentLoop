# Plan-driven Study: activation, evidence and release

Implemented by [ADR-0016](../adr/0016-roadmap-driven-study.md) and
[EPIC-29](../features/EPIC-29-roadmap-driven-study.md). Learner instructions and
portable-plan commands are in the [plan guide](../curriculum/workplace-plan-guide.md).

## Activate and use

The owner already has a saved personal plan. Press **Учиться** or `/study`.
For another admitted profile, `/roadmap activate` explicitly saves the default
plan; any validated roadmap edit also saves it. Merely viewing `/roadmap`
does not opt a profile in. A missing or invalid plan keeps the prior selector.
Admission, simple-mode delivery rules and automatic-message suppression stay as
described in [simple-learning.md](simple-learning.md).

The packaged bank has 144 module questions and 288 short writing situations:
48 modules × B2/B2+/introductory C1 × one choice and two written variants. There
is no DB import for this bank. Existing 270 adaptive and 86 reference questions
remain separate approved language practice. New module questions carry no
LearningItem target IDs; module evidence cannot graduate unrelated cards.

Personal plan controls:

- `general_share` balances answered choice questions, normally 60% general and
  40% work. Existing language questions consume work slots. Work modules and
  language practice interleave when both are available.
  A changed ratio uses evidence tagged with that ratio, avoiding catch-up debt
  from questions answered under a different allocation.
- `order`, `focus` and `paused` affect eligible future questions. Focus does
  not bypass a cooldown or C1 gate. A pending snapshot resumes unchanged.
- `weekly_minutes` suggests workload; it does not cap sessions or claim measured
  study time. Notes remain private reminders, not answer keys or grader prompts.
- If the desired strand has no eligible question, the other can be used. Small
  pools do not force immediate automatic repeats. The familiar-practice action
  remains explicit and does not turn repeated recognition into new mastery.

## Evidence and integrity

Each module's stage is derived from owned attempt records. Advancing from B2
requires correct recognition and two correct, genuinely evaluated independent
written variants at B2. The two situations must be on different local dates,
at least 24 hours apart. B2+ requires the same evidence; introductory C1 also
requires the original ten-topic strong-B2 gate.

The existing answer checker receives the complete self-contained situation and
target. A provider fallback stores an unchecked response without credit. Copied
choice examples, reused prior answers and copied model rewrites do not count as
independent work. These safeguards reduce false evidence; they are not an
external CEFR examination or a general plagiarism detector.

Optional writing uses a separate resumable BONUS session and the existing input
capture. The stream's pending choice is preserved; `/study` cancels the writing
capture and resumes the choice; an accepted next-choice tap also cancels capture.
Stale or invalid taps cannot cancel it. Progress/plan views preserve writing.
Failed, skipped and unchecked writing can be retried from the owned question;
repeating one variant does not create a second distinct situation.
External practice uses a separate `self_report`
attempt, idempotently tied to an owned answered question. It affects neither
writing evidence nor choice quotas. Text cannot assess pronunciation, live
interaction or unaided listening.

Issue reports quarantine the module question only for the reporting learner.
The bounded language-question maintainer does not automatically replace module
pack content. Change that public bank through reviewed repository edits.

## Edit and verify content

The public programme and larger practice briefs are in
`src/fluentloop/seeds/workplace_curriculum_v1.json`; choice keys, explanations
and short writing scenarios are in `roadmap_question_pack_v1.json` beside it.
Keep module IDs stable. Each stage has exactly three choices, a single correct
index, a Russian explanation, a meaningful English target and two distinct
self-contained English writing situations (`a`, `b`). General scenarios must
remain general, not a workplace question relabelled as general English.

```bash
uv run python scripts/workplace_plan.py --render docs/curriculum
uv run --extra dev pytest -q tests/test_roadmap_study.py tests/test_roadmap_study_ui.py
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests scripts
uv run python -m fluentloop --check
uv run python scripts/workplace_plan.py --check-render docs/curriculum
git diff --check
```

The offline editor publishes briefs, never reserved adaptive transfer questions
or answer keys. Run the isolated browser check from [testing.md](../testing.md)
after editing the template or renderer. Scan staged files before committing,
gated in the same command: `uv run python scripts/secret_scan.py && git commit ...`.

## Deployment and smoke

Use the [deployment procedure](deploy.md) with an exact reviewed commit and
passing CI. Preserve `.env`, `data/`, private plans and Telegram session files.
Take a verified SQLite online backup before changing the running release.
This feature has no schema migration or bulk progress rewrite.

In a transaction that is always rolled back, using the configured owner's
profile without printing private data:

1. Read the saved plan; confirm profile and evidence totals before the smoke.
2. Start Study, inspect the module/stage/strand and immutable snapshot. Change
   focus or pause that module; verify Study still resumes the pending question.
3. Answer the owned question once; reject the duplicate. Verify the following
   selection uses the changed plan and exposes module writing/external controls.
4. Start optional writing and use stub feedback; verify it remains unchecked.
   Resume Study and confirm the pending choice remains intact.
5. Report external completion twice; only one self-report is created. Confirm
   recognition, writing evidence and C1 access do not increase from the report.
6. Roll back; verify profile preferences and persistent attempt/item totals are
   unchanged. Check container health, startup logs and exact release SHA.

No artificial learner answers or unsolicited Telegram smoke messages should
remain. For application rollback, use the previous built image/commit and
preserve the database: the schema is unchanged. Private-plan import/export
provides a separate rollback for plan edits. Never restore an old DB snapshot
over newer real learner answers merely to revert application code.
