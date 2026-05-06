# EPIC-13 — Stats and weekly summary

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §19, §21 (`/stats`)
**Depends on:** EPIC-05, EPIC-06, EPIC-08, EPIC-11
**Blocks:** —

## Goal

Give the user visibility into their progress: counts of items, weak items,
session activity, recent grammar focus. Once a week, send a digest with
recommended next-week focus areas.

## In scope

- `/stats` command with the metrics from PRD §19:
  - total words / expressions / grammar rules / mistake patterns;
  - active vs archived counts;
  - completed vs skipped sessions (last 7 / 30 days);
  - weak items count;
  - due items count;
  - favorite items count;
  - last practiced date.
- All metrics are aggregations of existing tables — no new columns.
- Weekly digest: APScheduler job, fires once a week (default Sunday
  19:00 user TZ), composes a message that includes:
  - new items added this week (counts by type);
  - items practiced this week;
  - top 3 weak expressions / words;
  - grammar focus this week (most-touched concepts);
  - top recurring mistake (the highest-event-count
    `confidence=high` pattern);
  - recommended focus for next week (top 3 concepts with most active
    `low`/`high` patterns).
- The digest is a single Telegram message (or two if it overflows
  4096 chars).

## Out of scope

- Charts, plots, images — text-only MVP.
- CSV / Anki export — PRD §6 P1.
- Streak gamification — defer.
- Per-month / per-quarter aggregation — defer.

## Acceptance criteria

- `/stats` returns a well-formatted message with all PRD §19 metrics.
- Numbers match raw SQL queries against the underlying tables.
- The weekly job fires at the configured time and produces a message
  matching the structure above.
- "Recommended focus for next week" is non-empty when there are
  active mistake patterns; otherwise it's a graceful "you're on top
  of things — keep practicing" message.
- The digest message respects Telegram's 4096-char limit (split
  cleanly at section boundaries if needed).

## Open questions

- Day-of-week / time-of-day for digest — make it configurable via
  settings or hardcode? Default: hardcode Sunday 19:00 user TZ for
  MVP; revisit if it conflicts with the user's routine.
- Should the digest replace the daily reminder for Sunday or coexist?
  Default: coexist; they serve different purposes.

## Verification plan

1. With ~20 items and ~5 sessions of history, run `/stats`; manually
   spot-check counts against `sqlite3` queries.
2. Force the weekly job to fire (override the trigger time); inspect
   the resulting message for completeness and formatting.
3. With zero mistake patterns, confirm the digest's "recommended focus"
   degrades gracefully.
4. Generate a synthetic week with very long expressions to push past
   4096 chars; confirm clean split.

## Notes from implementation

- Added `/stats` aggregation and weekly summary text generation from existing
  tables.
- Telegram 4096-character splitting is not yet needed by the compact summary
  and should be added if real summaries grow.
