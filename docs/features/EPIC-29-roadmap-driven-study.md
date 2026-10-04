# EPIC-29 — Study follows the personal roadmap

**Status:** Done

**PRD references:** §6 P1, §14 Study follows the personal plan

**ADR:** [ADR-0016](../adr/0016-roadmap-driven-study.md)

**Follow-up:** [EPIC-30](EPIC-30-plan-driven-lexical-learning.md) adds the
reviewed lexical bank and supersedes the two-part recommendation with three
disjoint shares: 30% general, 40% work and 30% lexical. The delivered verification
below records the earlier release; module evidence and immutable resume remain.

## Scope

Connect all roadmap modules to the existing Study entrance with real contextual
choice practice, optional independent writing, honest external practice reports,
personal scheduling and module evidence. Keep the familiar one-question flow.

## Acceptance

- All 48 modules have reviewed B2/B2+/introductory-C1 practice material.
- General/work balance, focus, order and pauses affect actual next selection.
- Existing language practice remains reachable and retains its evidence gates.
- Questions resume across restarts; plan edits apply after the pending question.
- Written application advances modules only with genuine independent spaced work.
- Self-reports, skips, fallback feedback and repeated recognition cannot certify.
- Progress, plan/editor copy and learner/operational docs describe actual behavior.
- Automated tests, browser checks, CI and deployed rollback smoke pass.

## Delivered

`roadmap_study.py` reads a separate reviewed pack containing 144 contextual
questions and 300 self-contained short writing situations. Explicitly saved
plans enable selection; merely opening the plan does not change a profile.
General/work allocation uses answered practice units, with language questions
interleaved and both phrase and grammar categories retained. Changed ratios
start a fresh allocation history; current question snapshots stay resumable.

Module evidence separates recognition, independently checked writing and
external self-reports. Progress requires two distinct written applications on
different local dates at least 24 hours apart, plus recognition at that stage.
Copied examples, reused answers, model rewrites and fallback evaluations cannot
advance a module. Introductory C1 retains the ten-topic language evidence gate.

Telegram shows full A/B/C choices, optional writing and external-practice
actions, module progress and the next evidence needed. Writing can be retried
without losing the pending choice; stale callbacks cannot interrupt capture.
The editor, quick start, methodology, architecture and operational runbook now
describe the actual Study integration. No schema migration is required.

When **Хватит** ends a Study stream, the bot shows a compact result for that
session: correct answers, accuracy, general/work allocation and up to three
affected modules with their next evidence action. **Прогресс** and **План** are
available directly from this result. The copy explicitly keeps the summary out
of CEFR assessment; the complete evidence remains in the separate views.

## Verification

### Programme update

New plans recommend 70% workplace/supporting language practice and 30% general
English, with the client-facing track. Saved plans are preserved. The owner can
explicitly apply the ratio without resetting notes, pauses or evidence.
Six work modules have two additional C1 situations each (12 total); the stage
gate still needs two independently correct, spaced variants, not all four.
See [the programme and diagrams](../curriculum/learning-programme.md) and
[the comparative research](../research/curriculum-benchmark-2026-10.md).

The comparison covers 23 primary sources. Thirty-six public briefs in 12 modules
now supply facts, audience, constraints and output criteria. Four programme
diagrams were rendered and visually reviewed. The update gate passed **706 tests**,
Ruff, offline-editor browser checks, app construction and generated-view checks.

### Initial integration verification

- Full local gate: **658 tests passed**; Ruff, app construction, generated-view
  freshness and diff checks passed. Eight existing Alembic deprecation warnings.
- Isolated browser checks covered all 48 modules, controls, saved edits,
  import/export, invalid input, escaping and mobile layout; screenshots reviewed.
- Pack review covered all B2/B2+/introductory-C1 questions and written situations,
  including plausible distractors and stronger advanced-stage reasoning.
- Three authored samples checked with the configured live AI provider: a general
  and a client-facing response accepted; an off-topic response rejected. No real
  learner answers used. Verdict aliases and provenance have regression coverage.
- Wheel assets and local documentation links validated. Exact-commit CI and
  deployed checks follow [the release runbook](../runbooks/roadmap-study.md),
  which requires rollback of artificial smoke attempts and preservation of all
  learner preferences and evidence.
