# EPIC-02 — User profile and settings

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §8 (profile fields), §22 (scenarios), §21 (`/settings`)
**Depends on:** EPIC-01
**Blocks:** EPIC-07, EPIC-08

## Goal

The user has a persistent profile that drives the rest of the bot's behavior:
proficiency level, focus areas, timezone, preferred reminder time, daily
practice duration. The profile is created on first `/start` and editable
via `/settings`.

## In scope

- `User` table per PRD §24 with the fields listed in §8.
- On first `/start` (when no `User` row exists), create one with defaults:
  `level=B2+/C1-`, `focus_areas=[business, IT, conversational, grammar]`,
  `practice_duration_minutes=15`, `timezone` from `TIMEZONE` env var (or
  ask the user), `reminder_time` from `REMINDER_TIME_DEFAULT` env var.
- `/settings` shows current values and offers inline-button edits for:
  - Level (radio).
  - Focus areas (multi-select).
  - Reminder time (text input parsed as `HH:MM`).
  - Timezone (text input, validated against `pytz.all_timezones`).
  - Explanation language (RU / EN / mixed).
  - Daily practice duration in minutes.
- Settings changes persist immediately and confirm with a message.

## Out of scope

- Multi-user account management — PRD §6 explicitly excludes this from MVP.
- Onboarding wizard with multiple screens. Defaults are good enough; the
  user can edit via `/settings`.

## Acceptance criteria

- First `/start` from the allowed user creates a `User` row.
- Subsequent `/start` does not duplicate the row.
- `/settings` displays current values.
- Each editable field can be changed and the new value is reflected on
  the next `/settings`.
- Bot writes the updated `updated_at` timestamp on every change.
- Invalid timezone or reminder time values produce a user-friendly error
  and don't corrupt the row.

## Open questions

- Should `level` be an enum (`A2`, `B1`, `B2`, `C1`, `C2`) or free text?
  The PRD says default is `B2+/C1-`. Decision: enum with `B2`, `B2+`,
  `C1-`, `C1` for MVP. Anything else is a future enhancement.
- `school_days` field from PRD §8 — postpone to a later epic; not used by
  any MVP behavior yet.

## Verification plan

1. Start with empty DB. `/start` creates the row (verify with `sqlite3
   data/fluentloop.sqlite ".dump users"`).
2. `/settings` shows the defaults.
3. Change reminder time to `20:30`; `/settings` shows `20:30`.
4. Set timezone to `Europe/Berlin`; `/settings` confirms.
5. Restart container; settings persist.

## Notes from implementation

- Implemented persistent user defaults and validated setting updates through
  service functions used by the bot handlers.
- Added `/settings set <field> <value>` for practical Telegram-side edits;
  richer inline keyboard editing remains a later UX polish.
