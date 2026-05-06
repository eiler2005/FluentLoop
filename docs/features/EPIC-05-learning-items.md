# EPIC-05 — Learning items

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §10 (item types), §24 (data entities), §21 (`/add`)
**Depends on:** EPIC-02
**Blocks:** EPIC-04 (writes here), EPIC-06, EPIC-07, EPIC-09, EPIC-14

## Goal

The `LearningItem` table is the heart of the bot. This epic delivers the
table, its CRUD, the `/add` command for manual creation, and integration
points for `is_favorite`, `status`, and tagging.

## In scope

- `LearningItem` table per PRD §24: `id`, `user_id`, `type`, `text`,
  `meaning_ru`, `explanation`, `examples` (JSON list), `tags` (JSON list),
  `level`, `source_material_id` (nullable), `is_favorite`, `status`,
  timestamps.
- Item types from PRD §10: `word`, `expression`, `grammar_rule`,
  `mistake_pattern`.
- `status` enum: `active`, `archived`, `suspended`.
- `/add` command — interactive prompt for type, then text, meaning,
  optional tags. Creates a `LearningItem` directly (no candidate flow,
  user is explicit).
- Programmatic create-from-candidate path (used by EPIC-04 "Add all" /
  "Add one").
- Programmatic update / archive / suspend (no UI in this epic — used by
  later epics).
- `is_favorite` is a boolean; UI to toggle is in EPIC-14, but the column
  exists from day 1.

## Out of scope

- Listing / browsing learning items in chat — defer to EPIC-13 (`/stats`
  surfaces counts) and EPIC-14 (favorites listing).
- Inline editing in chat — the manual edit path lives in EPIC-04 (during
  approval) and `/add`. Bulk edit is a future enhancement.
- Web UI for management → EPIC-15 (deferred).

## Acceptance criteria

- `/add` walks the user through type, text, meaning, optional tags;
  creates a row with `status=active`.
- A row created via `/add` is indistinguishable from a row created via
  EPIC-04 approval (except `source_material_id` is null for `/add`).
- `archived` and `suspended` items are excluded from EPIC-07 generation
  and EPIC-06 scheduling.
- `examples` and `tags` are stored as JSON arrays and round-trip cleanly.
- Trying to add a duplicate `(text, type)` pair within the same user
  warns the user and offers "merge" / "keep separate".

## Open questions

- ORM choice: SQLAlchemy 2.x vs SQLModel vs Peewee. Default: SQLAlchemy 2.x
  (most familiar, works fine for SQLite). Consider an ADR if SQLModel
  becomes attractive.
- Migrations: Alembic from day 1, or manual schema evolution until things
  stabilize? Default: Alembic from day 1 — cheap insurance.
- `meaning_ru` vs `meaning` — PRD calls it `meaning_ru` but explanation
  language is configurable per profile (RU / EN / mixed). Keep the column
  named `meaning` and let `User.explanation_language` drive what gets
  written.

## Verification plan

1. `/add` → expression → `push back on` → meaning → `мягко возражать` →
   tag `meetings`. Verify row.
2. SQL check: `SELECT type, count(*) FROM learning_items GROUP BY type`
   returns expected counts.
3. Archive a row programmatically; confirm it disappears from any future
   EPIC-07 candidate set.
4. Try to add a duplicate; confirm the merge/keep-separate dialog.

## Notes from implementation

- Added `LearningItem` CRUD helpers, duplicate protection, status changes,
  favorite flag support, and automatic `ReviewState` creation.
- Added `/add type | text | meaning | tags` plus a one-step FSM prompt for
  manual item creation.
- Duplicate `/add` attempts now warn about the existing row and present the
  practical merge/keep-separate options for the Telegram MVP.
- Invalid `/add` payloads now return friendly Telegram errors.
- Add confirmations now include item ids so later commands can target items.
- Added `/items [active|archived|suspended]` and `/item archive|suspend|restore
  <item_id>` so the MVP can manage learning-item lifecycle from Telegram.
