# EPIC-16 — Learning Engine v1

**Status:** Done (2026-05-08)
**PRD references:** §13, §14, §15, §17, §18, §22.2
**Depends on:** EPIC-05, EPIC-06, EPIC-07, EPIC-08, EPIC-09, EPIC-11, EPIC-12
**Blocks:** EPIC-17, EPIC-19, EPIC-21

## Goal

Refactor `/today` so it starts a staged 15-minute English practice session
instead of a flat list of unrelated exercises. The session should still use
existing learning items, SRS, mistake patterns, grammar concepts, practice
sessions, and attempts.

## In scope

- Add `src/fluentloop/learning_engine.py` as a thin orchestration layer.
- Support session modes: `review`, `lesson`, `mixed`, `mistake_focus`.
- Generate about seven stages: `warmup`, `input`, two
  `controlled_practice`, `grammar_or_mistake_focus`, `free_production`, and
  `recap`.
- Include metadata on every exercise: stage, mode, topic, lesson goal, target
  skill, and target item ids.
- Update Telegram rendering so `/today` shows mode, topic, goal, and
  `Step X/7 — Stage name`.
- Keep deterministic seed fillers only as fallback.

## Out of scope

- Persistent lesson-plan tables.
- DeepSeek calls and AI-generated exercises.
- Grammar schema changes and material context search.

## Acceptance criteria

- `/today` starts successfully and shows a 15-minute session header.
- Sessions have about seven staged steps and each step has stage metadata.
- Due items are prioritized over random active items.
- Active mistake patterns can influence the session.
- Existing answer checking, SRS updates, `PracticeSession`, and
  `PracticeAttempt` behavior continue to work.
- The recap stage asks for active recall.

## Verification plan

- Unit tests for mode selection, item scoring, staged session composition,
  metadata, due-item priority, seed fallback, and practice/attempt flow.
- Live smoke: deploy, run `/today`, verify header and staged prompts, answer at
  least two steps, confirm attempts and SRS updates, and inspect logs.

## Notes from implementation

- Added `src/fluentloop/learning_engine.py` with mode selection, item scoring,
  topic/goal selection, and seven staged exercise builders.
- `/today` now renders a 15-minute header with mode, topic, and goal, then
  serves `Step X/7 - Stage name` prompts.
- Exercise dicts keep the existing `target_learning_item_ids` contract and add
  stage metadata for the new Learning Engine.
- Deterministic seed prompts remain as fallback; existing answer checking,
  SRS, and attempt creation continue to use the existing flow.
- Increased source material upload cap to 20 KB so the provided first lesson
  markdown can be stored as one `SourceMaterial`.
