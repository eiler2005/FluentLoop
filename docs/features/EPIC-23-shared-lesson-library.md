# EPIC-23 — Shared Lesson Library

- **Status:** Planned
- **Owner:** Denis Ermilov
- **Depends on:** EPIC-17 (persistent lesson plans), ADR-0008
- **Blocks:** ADR-0009 (admission policy), public discovery of bot

## Why

Production currently holds 21 owner-curated lesson plans built from 34
uploaded source materials, all owned by `user_id=2`. They cover the
business/IT communication territory the bot is designed for (diplomatic
pushback, incident updates, RFC trade-offs, postmortems, performance
feedback, async communication, deadline negotiation, exec summaries,
etc.). Other admitted users currently see none of them — every user is
expected to upload their own material from scratch.

The owner wants this content to function as a **shared library**:
discoverable by any admitted user, subscribable on demand, with a clean
per-user progress slate.

## Scope

In:

- New flags on `lesson_plans`: `is_template` (bool) and `template_of`
  (nullable FK to the template plan a row was cloned from).
- Mirror flags on `source_materials` and `learning_items` so the clone
  path can find what to copy.
- `/library` command — list of all `is_template=true` plans, paginated,
  showing topic + title + short description.
- `/subscribe <plan_id>` command (also reachable from `/library`
  inline buttons) — copies the template plan, its `lesson_plan_items`,
  the underlying `learning_items`, and the relevant `source_materials`
  rows into records owned by the current user.
- Existing `/lessons`, `/lesson`, `/today` keep working unchanged
  because they already filter by `user_id`. Clones look identical to
  user-uploaded plans from their point of view.
- Mark all 21 current plans (and their materials/items) on `user_id=2`
  as templates via a one-off migration step.
- Owner-only path to author new templates: existing upload flow
  produces a `user_id=2` plan; an admin command (`/publish <plan_id>`)
  flips it to `is_template=true`.

Out (explicit non-goals for this epic):

- Admission policy. Right now `TELEGRAM_ALLOWED_USER_ID` admits the
  owner only; opening the bot to other Telegram users needs ADR-0009
  first. EPIC-23 may proceed before ADR-0009 — the library will just
  have only one subscriber until admission opens.
- Template versioning / refresh-from-template. Edits to a template
  after the fact will not auto-propagate to existing subscribers.
- Re-attempting the 13 source materials that failed to draft a plan
  (`_draft_lesson_plan` returned None). Separate pass.
- Federated discovery across instances. Single bot, single library.

## Acceptance criteria

1. Schema migration adds `lesson_plans.is_template`,
   `lesson_plans.template_of`, `source_materials.is_template`,
   `source_materials.template_of`, `learning_items.is_template`,
   `learning_items.template_of`. All default `is_template=false`,
   `template_of=NULL`.
2. One-off data step marks plans `5,7,8,9,10,11,12,13,14,15,16,17,18,
   19,20,21,22,23,24,25,26` as `is_template=true`, plus their linked
   materials and items.
3. `/library` returns a paginated list of templates with topic, title,
   and template id. Empty case shows a "no templates yet" message.
4. `/subscribe <template_id>` creates a new `LessonPlan` row with the
   current user's `user_id`, `template_of=<template_id>`,
   `is_template=false`, and clones all referenced items/materials with
   the same `template_of` linkage. Returns a confirmation with the
   new plan's id, ready for `/lesson <id>`.
5. Subsequent `/today`, `/lesson`, `/practice` runs use the cloned
   records; no read or write ever touches another user's records.
6. Owner running `/publish <plan_id>` on a non-template plan they own
   sets `is_template=true` and cascades to materials/items. Idempotent.
7. Cloning the same template twice produces two independent
   subscriptions (no dedupe). UI should warn but not block.
8. Existing queries in `src/fluentloop/lesson_plans.py` need no
   modification — verify by running `pytest -q` after the migration
   and confirming all existing tests still pass.

## Open questions

- `/library` filtering — by topic / cluster / level? V1: flat list,
  ordered by `created_at DESC`. Revisit after first multi-user
  feedback.
- Should `practice_session_cached` be cleared on subscribe? Yes — the
  user gets a fresh slate; do this in the clone path.
- Notification when a new template appears? Probably yes, but only
  after ADR-0009 admission policy lands.

## Verification plan

- Local: seed a fresh DB with two users (`user_id=2` owner, `user_id=3`
  subscriber). Mark a plan as template under `user_id=2`. Run
  `/subscribe` as `user_id=3`. Verify the clone appears in
  `available_lesson_plan(user_3)`, completes a session via existing
  `/today`, and `practice_attempts` / `review_states` rows for
  `user_id=3` reference cloned items, not the original templates.
- Re-run `scripts/seed_b2_curriculum.py` and `scripts/seed_demo_data.py`
  to confirm seed paths still work.
- On VPS: run the migration in dry-run mode (script + `--no-commit`)
  against a copy of production SQLite before applying.
