# Plan-driven lexical learning

This runbook covers [EPIC-30](../features/EPIC-30-plan-driven-lexical-learning.md)
and [ADR-0017](../adr/0017-plan-driven-lexical-learning.md). It documents the
implementation and release checks; it does not assert that a deployment has
already enabled the feature for a live profile.

## Enable or adjust a personal plan

For an admitted simple profile with a saved roadmap:

```text
/roadmap
/roadmap general 30
/roadmap lexical 30
/study
/progress
```

If no plan is saved, use `/roadmap activate` first. New plans use the
`client_facing` track and **30% general / 40% work / 30% lexical**. Legacy
version-1 plans without `lexical_share` validate with zero; viewing the plan
does not replace those settings. Change only the authorised profile and the
requested fields, preserving track, order, focus, pauses, notes and other
preference namespaces.

These are three disjoint buckets of normal answered questions. A lexical task
with a workplace context counts only as lexical. Its share includes new senses
and spaced review. Work equals `100 - general_share - lexical_share`; general
is 20–90, lexical 0–60, and their sum cannot exceed 90. Setting lexical to zero
disables future lexical selection while retaining history and a pending snapshot.
Changes begin a new allocation cohort; they do not reset evidence.

The [offline planner](../curriculum/workplace-planner.html) exposes the same
shares and validation. Its JSON must be explicitly applied to the bot using
the [plan import/export instructions](../curriculum/workplace-plan-guide.md#4-перенести-между-файлом-и-профилем).
Export the current profile first and keep that private copy for rollback.
Weekly minutes are a planning aid; the bot balances questions, not time.

## Content source and editing

The editable public source is
[`workplace_lexicon_v1.json`](../../src/fluentloop/seeds/workplace_lexicon_v1.json).
Read [lexical-bank.md](../curriculum/lexical-bank.md) for the rendered bank,
[lexical-programme.md](../curriculum/lexical-programme.md) for the learning route,
and [the research](../research/workplace-lexical-learning.md) for sources and limits.

The validated initial bank contains **240 senses in 16 functions: 180 work and
60 general**. Each sense has two recognition variants and two production tasks:
**480 of each**. Twenty entries have an introductory-C1 task label.

Each entry represents one sense or construction, with a stable ID, contextual
strand, function, module references and task stage. It carries Russian and
English meanings, an original example, grammar frame, register, plain alternative,
source attribution, two recognition variants and two independent writing tasks.
Do not merge distinct meanings into one ambiguous card. Do not rename stable
IDs to make cosmetic edits; attempts refer to those IDs. Existing snapshots
remain immutable when the public source changes.

Stage labels are editorial curriculum placement and intended task demand,
not calibrated CEFR levels or dictionary-certified phrase levels.
Keep work and life contexts covered; the lexical strand is truthful content
metadata, not a second allocation axis. Verify meanings and grammar against
the attributed primary source and review answer ambiguity, distractors, example
naturalness, register and distinct task contexts before release. The validator
checks structure and references; it does not replace editorial source review.

From the repository root, without applying profile changes:

```bash
uv run python scripts/lexical_bank.py
uv run python scripts/lexical_bank.py --bank src/fluentloop/seeds/workplace_lexicon_v1.json
uv run python scripts/lexical_bank.py --render docs/curriculum
uv run python scripts/lexical_bank.py --check-render docs/curriculum
uv run --extra dev pytest -q tests/test_lexical_learning.py tests/test_workplace_roadmap.py tests/test_roadmap_study.py
```

Render after editing the bank; commit the source and generated views together
only after the normal review and secret gate. Editing the programme Markdown
alone changes guidance, not the packaged bank or a learner's saved preferences.
The bank supplies reviewed Study snapshots without new active LearningItems,
database migration or scheduled learning pushes.

## Selection, feedback and evidence

- The selector alternates unseen senses and due reviews when both are eligible.
  Active module references, focus, order, pauses and the existing ten-topic C1
  gate constrain selection. Unavailable pools produce an explicit fallback
  annotation; quotas do not justify early repeats.
- After successful recognition, the whole sense waits at least 24 hours and
  a different local date. After failure or unknown, five other normal questions
  must be answered. Sibling variants share these limits.
- Feedback teaches Russian and English meaning, example, grammar, register
  and a plain alternative. Optional writing uses the existing BONUS capture
  and genuine answer checker.
- Recognized status requires two different successful recognition variants
  on different local dates at least 24 hours apart. Independent-use status
  requires two different genuine, correctly checked independent writing tasks
  with the same spacing and the target used naturally.
  Production tasks explicitly supply the target expression. Independence means
  independently authored guided application, not uncued spontaneous retrieval;
  report the milestone with that limitation.
- Copied examples, answer choices, prior answers, model rewrites, unchecked
  fallback and familiar responses do not establish these milestones. Familiar
  practice selects previously answered questions and supplies neither mastery
  nor allocation credit. Lexical milestones never advance module/adaptive
  mastery or unlock C1.
- `/progress` and session results distinguish exposure, recognition, writing
  and new/review counts. These are local practice indicators, not CEFR
  certification or evidence of assessed speech/listening.
- **Ошибка в вопросе** quarantines that sense and its variants only for the
  reporting user. It retains history and public content; the automatic adaptive
  variant maintainer does not rewrite this bank.

## Release smoke and rollback

Run the [standard gate](../testing.md), real-bank validation and generated-view
checks. Verify the downloadable editor on desktop/mobile: edit both shares,
reject totals above 90, import a legacy zero-share plan, and round-trip JSON.
Inspect package contents so the bank is present in the built artifact.

Use a rolled-back transaction against the authorised profile for handler smoke.
Check a lexical question's sense ID, truthful context and allocation bucket;
answer once and reject duplicate/foreign callbacks. Inspect teaching feedback,
optional writing and progress. Change shares while pending and confirm the
original snapshot resumes. Exercise issue reporting, zero share and unavailable
pools with isolated data. Use fixed-time tests for 24-hour/local-day milestones,
not artificial live learner evidence. Do not send unsolicited smoke messages.

For an authorised release, make a consistent private SQLite backup, preserve
the profile export, deploy the reviewed revision and enable only the requested
owner allocation. Inspect other profiles for unchanged preferences. A code
rollback plus reimport of the private previous plan restores prior selection;
do not erase attempts or delete data. Existing live lexical snapshots and
attempts must remain inspectable. Deployment and profile changes require the
explicit release authorisation described in the repository rules.
