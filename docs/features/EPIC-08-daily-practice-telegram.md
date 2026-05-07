# EPIC-08 — Daily practice in Telegram

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §14, §22.2 (daily practice scenario), §21 (`/today`,
`/review`)
**Depends on:** EPIC-07
**Blocks:** EPIC-10, EPIC-13

## Goal

The user starts their day, gets a reminder at their preferred time, opens
the bot, runs through 7 exercises, and finishes with a short summary. The
session must feel snappy (cached batch from EPIC-07, no AI wait at the
start) and survivable: leaving mid-session and coming back hours later
just resumes where they left off.

This epic also owns the daily SQLite backup, since both run on APScheduler.

## In scope

- `/today` command — fetch today's cached session (EPIC-07) and start
  serving exercises one by one.
- Reminder cron — APScheduler job at the user's `reminder_time` in their
  `timezone`, fires a "ready for today's English?" message with an
  inline button to start.
- Session state in the DB (not in-memory): `PracticeSession` per PRD §24
  with `started_at`, `completed_at`, `status` (`in_progress`,
  `completed`, `abandoned`).
- Each exercise becomes a `PracticeAttempt` row when answered.
- Resume logic: if the user fires `/today` and there's an
  `in_progress` session for today, continue from the next unanswered
  exercise (don't restart).
- Session summary on completion: how many correct / partial / incorrect,
  what the next-review schedule looks like, key feedback highlights.
- `/review` command — start an ad-hoc session of due items only,
  generated on demand from EPIC-07's logic.
- Daily SQLite backup job (APScheduler):
  - Snapshot `data/fluentloop.sqlite` to
    `data/backups/db-YYYY-MM-DD.sqlite` after the bot's quiet hours.
  - Keep last 14 days; delete older.

## Out of scope

- Voice input / output — PRD §6 P2.
- Push notifications outside Telegram — Telegram is the channel.
- Real-time multi-user contention — single user.
- Off-VPS backup (B2 / restic) — P1.

## Acceptance criteria

- At `reminder_time` in the user's TZ, the bot sends the reminder
  message with a "Start" button.
- Pressing "Start" or sending `/today` begins the session and presents
  exercise 1/7.
- After answering, the bot shows feedback (placeholder until EPIC-10)
  and presents the next exercise.
- Closing Telegram after exercise 3 and returning hours later via
  `/today` resumes at exercise 4.
- Completing all 7 exercises produces the summary message and marks
  the session `completed`.
- The next day's `/today` starts a fresh session (yesterday's session is
  not "in progress").
- Backup files appear in `data/backups/` once per day; the 15th-oldest
  is deleted on the day it would become 15 days old.

## Open questions

- What if the cached session is stale (user has uploaded new material
  between pre-gen and morning)? See EPIC-07 open question.
- Reminder during ongoing in-progress session: skip or remind anyway?
  Default: skip if there's an `in_progress` session created within the
  last 24h.
- Exact time-of-day for the backup job: default `04:00` user TZ, before
  the next pre-gen run.

## Verification plan

1. Set `reminder_time` to "two minutes from now"; wait — confirm the
   reminder.
2. Press "Start"; answer 3 exercises; close Telegram; reopen 1 hour
   later; `/today`; confirm resume at exercise 4.
3. Complete the session; confirm summary and `completed_at` in DB.
4. Run pre-gen for "tomorrow" + jump the system clock — confirm next
   day's session is independent.
5. Wait one day after first run; `ls data/backups/` shows the snapshot.
6. Simulate 16 days of operation; confirm rotation deletes the oldest
   snapshot.

## Notes from implementation

- Implemented `/today`/`/review` handler path, persisted sessions/attempts,
  resume behavior, summaries, and SQLite backup helper.
- Added APScheduler registration for daily reminders, overnight pre-generation,
  and daily SQLite backups.
- Tightened answer handling so random free text no longer silently starts a
  practice session; answers require an active `/today`/`/review` session.
- Completion feedback now includes a persisted attempt summary with correct,
  partial, incorrect, and answered counts.
- Reminder messages now include a Telegram `Start` inline button wired to the
  same `/today` session-start path.
- Channel-mode practice messages use logical channel topics in the message
  text: `#practice_flow`, `#feedback`, `#next_prompt`, `#summary`, and
  `#mistakes`. Native Telegram forum topics remain out of scope for a channel;
  they require a forum supergroup.
- Audit coverage verifies all seven attempts complete a session and set
  `completed_at`.
