# EPIC-17 — Persistent LessonPlan v1

**Status:** Done (2026-05-08)
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
- Store teacher-style lesson overview metadata: title, topic, goal, language
  focus, knowledge areas, and planning rationale when available.
- Let `/today` run a lesson-mode session from an available active lesson plan,
  with fallback to EPIC-16 composition.
- Add lesson browsing/start commands:
  `/topics`, `/lessons [query]`, `/lesson <id>`, `/lesson random`, and
  `/lesson topic <query>`.
- Add a repo-backed deterministic B2/B2+ business/IT curriculum seed with
  20 active lesson plans and a Markdown export.

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
- The user can inspect active lesson plans and start a selected, random, or
  topic-matched lesson explicitly.
- The seed command creates exactly 20 B2/B2+ lessons idempotently without a
  DeepSeek key.
- Approving a new lesson material makes that active lesson plan available to
  today's practice immediately; stale older daily sessions may be superseded.

## Verification plan

- Unit tests for lesson-plan creation, step ordering, item links, `/today`
  lesson-plan selection, and fallback.
- Live smoke: back up the DB, apply schema changes, create a lesson plan from
  lesson material, run `/today`, complete at least two steps, verify attempts
  and SRS, and check logs.

## Notes from implementation

- Added `LessonPlan`, `LessonStep`, and `LessonPlanItem` as additive SQLite
  tables managed through the existing `Base.metadata.create_all` startup path.
- Added deterministic lesson-plan helpers that infer topic/goal from source
  material and link existing learning items instead of duplicating them.
- Approval now creates an active lesson plan when approved items exist for a
  source material.
- The Learning Engine now prefers an available lesson plan and annotates
  exercises with `lesson_plan_id` and `lesson_step_id`, while preserving
  fallback staged composition.
- Approved lesson materials can now use a teacher-style DeepSeek lesson draft
  to set topic, goal, language focus, step instructions, item priority, and
  rationale; deterministic planning remains the fallback.
- A lesson plan is treated as one reusable pool of approved items. `/today`
  samples 15-20 micro-drills from that pool using teacher priority, SRS due
  state, novelty, and recent-practice penalty.
- The Telegram practice header now displays the selected LessonPlan title, so
  the user can tell which uploaded lesson is driving the current exercises.
- Added a lesson browser over active lesson plans and knowledge areas:
  `/topics`, `/lessons [query]`, `/lesson <id>`, `/lesson random`, and
  `/lesson topic <query>`.
- Added `scripts/seed_b2_curriculum.py` and
  `docs/curriculum/b2_b2plus_lesson_catalog.md` as a deterministic 20-lesson
  B2/B2+ business/IT seed catalog for offline curriculum population.
