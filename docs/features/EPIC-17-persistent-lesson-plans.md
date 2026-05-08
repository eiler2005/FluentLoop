# EPIC-17 — Persistent LessonPlan v1

**Status:** Planned
**PRD references:** §9, §10, §13, §14, §22.1, §24
**Depends on:** EPIC-16
**Blocks:** EPIC-18, EPIC-19, EPIC-21

## Goal

Let uploaded `SourceMaterial` become a reusable 15-minute lesson plan, not only
a source of approved `LearningItem` rows.

## In scope

- Add `LessonPlan`, `LessonStep`, and `LessonPlanItem` models.
- Link lesson plans to `SourceMaterial` and target items without duplicating
  `LearningItem` data.
- Create deterministic draft lesson plans from source material and approved
  items.
- Let `/today` run a lesson-mode session from an available active lesson plan,
  with fallback to EPIC-16 composition.

## Out of scope

- DeepSeek-generated lesson plans.
- Full curriculum scheduling.
- Destructive migration or cleanup of existing practice data.

## Acceptance criteria

- A `SourceMaterial` row can be linked to a `LessonPlan`.
- Ordered `LessonStep` rows represent the staged practice flow.
- `LessonPlanItem` links target, supporting, review, grammar-focus, or
  mistake-focus items to a plan.
- `/today` can use an active lesson plan while preserving SRS and
  `PracticeAttempt` behavior.

## Verification plan

- Unit tests for lesson-plan creation, step ordering, item links, `/today`
  lesson-plan selection, and fallback.
- Live smoke: back up the DB, apply schema changes, create a lesson plan from
  lesson material, run `/today`, complete at least two steps, verify attempts
  and SRS, and check logs.

