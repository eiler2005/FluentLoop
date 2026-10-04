# EPIC-28 — Research-backed editable workplace roadmap

**Status:** Done — implemented and locally verified  
**PRD references:** §6 P1, §14 Editable workplace roadmap  
**ADR:** [ADR-0015](../adr/0015-editable-workplace-roadmap.md)

**Follow-up:** [EPIC-29](EPIC-29-roadmap-driven-study.md) connects this plan to
actual Study questions and module writing. The delivered notes below describe
the original EPIC-28 release; its advisory-only selector limit is superseded.

## Scope

Research official CEFR, language assessment and workplace learning sources;
keep general English as the foundation with additional client/business/IT
B2–B2+–introductory C1 modules; provide an editable
personal plan and practical task ladder with honest delivery and evidence labels.

## Acceptance

- Primary sources support the coverage framework; authored targets are identified.
- Every module has three stage outcomes/tasks, evidence criteria and resources.
- Existing adaptive coverage and external/planned practice are distinguished.
- Users can choose a track/time budget, reorder/pause modules and edit notes in
  an offline planner; portable imports validate before applying per-user prefs.
- Telegram shows the plan and supports common personal changes.
- Imports cannot alter assessments, history, adaptive gates or other users.
- Tests cover validation, isolation, rendering, personal edits and bot routing;
  documentation explains starting, editing, applying and limitations.

## Delivered and verified

- Two primary-source research reports and an authored 48-module catalogue:
  16 general, 32 supplementary work modules, 144 stage tasks, 26 language-map
  entries and three complete tracks. The initial time split was 60/40; the
  EPIC-29 recommendation was 30% general / 70% work. The current three-part
  30% general / 40% work / 30% lexical programme is defined in
  [EPIC-30](EPIC-30-plan-driven-lexical-learning.md).
- `/roadmap` view and personal controls; offline responsive editor with filtering,
  stage tasks, ordering, pauses, notes and portable JSON. An explicit owner CLI
  validates/applies imports and exports the current private plan.
- Existing 270 adaptive and 86 legacy questions remain unchanged. The wide
  programme adds practice briefs, not a new assessed question bank. External
  listening/speaking and unimplemented bank coverage are clearly labelled.
- Independent content review covered all 144 tasks and corrected a delivery
  label/resource mismatch and a missing C1 follow-up requirement.
- On 2026-10-03: 591 Python tests passed, eight existing Alembic warnings;
  Ruff, application construction, generated-view freshness and wheel packaging
  passed. Isolated headless Chrome checked editing, pause/resume, persistence,
  JSON roundtrip, invalid/duplicate-key imports, safe note rendering and mobile
  overflow. Desktop/mobile screenshots were visually inspected.

See [usage and editing](../curriculum/workplace-plan-guide.md),
[research](../research/README.md), [ADR-0015](../adr/0015-editable-workplace-roadmap.md)
and [verification](../testing.md). Deployment follows a consistent database
backup; initial owner plan preferences must preserve all learning history and
other profiles. A rollback smoke verifies this without retaining test changes.
