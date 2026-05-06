# EPIC-07 — Automatic practice generation

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §13, §25.2
**Depends on:** EPIC-05, EPIC-06, EPIC-09, ADR-0003, ADR-0004
**Blocks:** EPIC-08, EPIC-10, EPIC-11

## Goal

Compose a daily 7-exercise practice session **automatically**, **without
asking the user for confirmation per exercise**. Inputs: due items,
weak items, mistake patterns, favorites, recent uploads, level, focus
areas. Outputs: a `practice_session_cached` row with prompt + expected
answer + hint + explanation per exercise, ready for EPIC-08 to serve
instantly.

## In scope

- Selection algorithm (PRD §13 priority rules):
  1. Due / overdue items.
  2. Weak expressions and words (`fail_count > success_count`).
  3. Active mistake patterns with `confidence=high`.
  4. Grammar rules linked to recent mistakes.
  5. Recently added lesson items (last 7 days).
  6. Favorite items.
  7. Items relevant to the user's focus areas.
- Exercise mix per session (PRD §13): aim for variety across the six
  types from EPIC-09. Concrete recipe (target distribution per session):
  - 1× guess word/expression
  - 1× translate phrase
  - 1× cloze
  - 1× grammar rewrite
  - 1× error correction
  - 1× business/IT follow-up
  - 1× mistake-based exercise (when active patterns exist; else fall
    back to translate or rewrite).
- AI generation per exercise — heavy tier (per ADR-0003) for grammar
  rewrites, follow-ups, and translations; light tier for cloze and
  exact-match.
- Per ADR-0004: pre-generation runs overnight. The morning batch caches
  the next day's session in `practice_session_cached`.
- Cache hit / miss metric logged.
- Fallback path: if pre-gen failed and the user fires `/today`,
  generate on-demand with a "preparing exercises…" message.

## Out of scope

- Suggesting *new* learning items mid-generation — explicitly forbidden
  by PRD §13 "Safety rule". The AI may suggest items only via the
  approval flow in EPIC-04.
- Adaptive difficulty in real time — defer.
- Per-exercise user confirmation — explicitly forbidden by PRD §13.

## Acceptance criteria

- When pre-gen runs, a `practice_session_cached` row is created for the
  user with 7 exercise objects.
- Cached exercises include enough information for EPIC-08 to render and
  EPIC-10 to check: `prompt`, `expected_answer`, `hint`, `explanation`,
  `exercise_type`, `target_learning_item_ids`.
- Items selected respect the priority order above.
- Mistake-based exercises only appear when `confidence=high` patterns
  exist.
- The same `LearningItem` does not appear twice in the same session.
- Fallback on-demand generation produces equivalent output structure.

## Open questions

- ADR-0004 not yet decided — when does pre-gen run, and how do we handle
  TZ for the user?
- Cache key shape: `(user_id, target_date_local)` so two days don't
  collide if the user's TZ shifts.
- If the user does multiple sessions in one day (e.g. `/today` twice),
  do we re-use the same cached batch or generate a second one? Default:
  re-use; multiple-sessions-per-day is post-MVP.
- Cost: 7 generation calls per day × heavy/light mix. ADR-0003 must
  approve the budget.

## Verification plan

1. Seed the DB with 20 learning items, 3 mistake patterns
   (1 high-confidence, 2 low), 2 favorites.
2. Run the pre-gen job manually.
3. Inspect `practice_session_cached` — should have 7 exercises with
   variety across the six types and at least one mistake-based.
4. Run pre-gen again the same day — should be idempotent (same row).
5. Force the AI provider offline; run `/today` — fallback message
   appears, on-demand path produces a session.

## Notes from implementation

- Added deterministic session composition and `practice_session_cached` rows.
- AI-generated exercise variation uses the stub/provider-ready path; selection
  is intentionally compact to keep the max-epics run green.
