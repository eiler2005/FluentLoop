# EPIC-23 — Shared Lesson Library

- **Status:** Done — seed catalog templates, English for Tech, subscribe clones, lesson types, public catalog export, learner docs, deploy, and smoke validated
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

Implementation note: the first rollout published the deterministic B2/B2+ seed
catalog (`curriculum:b2-b2plus`) before adding the owner-curated English for
Tech public series. Private owner uploads remain private unless explicitly
published later by the owner.

Current public catalog v1 contains the deterministic B2/B2+ seed catalog, the
owner-curated English for Tech series, and 40 code-defined business/IT scenario
cards. Markdown/HTML exports live in `docs/lesson-catalog/` and are generated
from SQLite/code, not edited by hand.

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
- Publish only deterministic B2/B2+ seed catalog plans tagged
  `curriculum:b2-b2plus` into the first public library.
- Display a learner-facing Lesson Type and target mix in `/library` and
  `/lesson <id>` so users can see whether a lesson trains vocabulary, chunks,
  grammar, mistakes, diplomatic tone, reading, writing, scenario rehearsal, or
  mixed recall.
- Export public catalog views with
  `scripts/export_lesson_catalog.py --public-only --html --out docs/lesson-catalog`.
  Public exports include shared templates and scenario cards only; private
  uploads, raw source text/PDFs, user answers, and reflections are excluded.
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
2. Seed-library publish step creates/updates the deterministic 20-lesson
   B2/B2+ catalog under the internal seed-library user and marks only plans
   tagged `curriculum:b2-b2plus` as `is_template=true`, plus their linked
   materials and items. Owner-curated public series such as English for Tech
   use explicit `series:*` tags.
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
7. Cloning the same template twice produces two independent lesson-plan
   subscriptions, while already cloned per-user source materials and learning
   items are reused safely under the existing uniqueness constraints.
8. Existing personal lesson queries exclude template rows so `/topics`,
   `/lessons`, `/lesson`, and `/today` operate on user-owned active plans.
9. `/library`, template details, and `/lesson <id>` show lesson type and target
   mix.
10. `docs/lesson-catalog/` can be regenerated from DB/code and contains public
    Markdown/HTML pages for lesson types, B2/B2+ seed lessons, English for
    Tech, and exactly 40 scenario cards.

## Open questions

- `/library` filtering — by topic / cluster / level? V1: flat list with optional
  text query over title/topic/goal/focus/tags, ordered by title. Revisit after first multi-user
  feedback.
- Should `practice_session_cached` be cleared on subscribe? Done — the
  user gets a fresh slate in the clone path.
- Notification when a new template appears? Probably yes, but only
  after ADR-0009 admission policy lands.

## Verification plan

- Local: `pytest -q` covers seed publish, `/library`, details callbacks,
  `/subscribe`, duplicate subscribe reuse, private visibility, owner-only
  `/publish`, lesson-type display, catalog export privacy, scenario count, and
  migration roundtrip.
- VPS: production SQLite was backed up, migration was verified on a copied DB,
  deploy applied `0002_epic23`, seed library publish created 20 template plans,
  20 template sources, and 80 template learning items, and handler smoke passed
  through `/library -> details -> subscribe -> /lessons -> /lesson start`.
