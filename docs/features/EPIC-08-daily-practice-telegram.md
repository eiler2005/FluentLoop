# EPIC-08 — Daily practice in Telegram

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §14, §22.2 (daily practice scenario), §21 (`/today`,
`/review`, `/practice`, `/topics`, `/lessons`, `/lesson`)
**Depends on:** EPIC-07
**Blocks:** EPIC-10, EPIC-13

## Goal

The user starts their day, gets a reminder at their preferred time, opens
the bot, runs through a 15-minute lesson of about 15-20 micro-drills, and
finishes with a short summary. The session should prefer the active lesson
pool when one exists, remain snappy, and stay survivable: leaving mid-session
and coming back hours later resumes the right local-day session.

This epic also owns the daily SQLite backup, since both run on APScheduler.

## In scope

- `/today` command — fetch today's cached session (EPIC-07) and start
  serving exercises one by one.
- Reminder cron — APScheduler job at the user's `reminder_time` in their
  `timezone`, fires a "ready for today's English?" message with an
  inline button to start.
- Session state in the DB (not in-memory): `PracticeSession` per PRD §24
  with `started_at`, `completed_at`, `status` (`in_progress`,
  `completed`, `abandoned`, `superseded`).
- Each exercise becomes a `PracticeAttempt` row when answered.
- `/skip` and inline skip button — records a skipped `PracticeAttempt`,
  reveals the correct answer/explanation, and advances to the next prompt.
- Resume logic: if the user fires `/today` and there's an
  `in_progress` session for today, continue from the next unanswered
  exercise. If a stale legacy session conflicts with a newly active
  LessonPlan, mark it `superseded` and start the lesson-plan session.
- Session summary on completion: how many correct / partial / incorrect,
  skipped and answered counts, what the next-review schedule looks like,
  key feedback highlights.
- `/review` command — start an ad-hoc session of due items only,
  generated on demand from EPIC-07's logic.
- `/practice vocab|grammar|mistakes|writing|review|mixed` — start an
  explicit standalone session by user-facing mode.
- `/topics`, `/lessons [query]`, `/lesson <id>`, `/lesson random`, and
  `/lesson topic <query>` — browse lesson pools and explicitly start a
  selected/random/topic-matched lesson.
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
  exercise 1/N, where N is usually 15-20 micro-drills for a 15-minute lesson.
- After answering, the bot shows feedback (placeholder until EPIC-10)
  and presents the next exercise.
- Closing Telegram after exercise 3 and returning hours later via
  `/today` resumes at exercise 4.
- Completing all 15-20 micro-drills produces the summary message and marks
  the session `completed`.
- Sending `/skip` during practice reveals the expected answer and explanation,
  records a skipped attempt, and advances the session.
- The next day's `/today` starts a fresh session (yesterday's session is
  not "in progress"). The day boundary is based on the user's configured
  timezone, not UTC.
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
- Forum workspace mode is now supported for the `FluentLoop English Forum`
  supergroup. When `TELEGRAM_FORUM_GROUP_ID` and topic env vars are present,
  the bot routes practice/help/materials/feedback/next-prompt/summary/mistake
  messages to real Telegram topics via Bot API `message_thread_id`.
- `FluentLoop English` remains the announcement/digest channel; the forum
  group is the primary study workspace.
- `/start` now also posts channel hub messages when channel mode is configured:
  a `#practice_flow` practice entry point and a `#materials_upload` lesson
  material inbox. Channel buttons start practice or open the private upload
  flow for text entry.
- `/start` and `/help` also post a `#help` channel message explaining the
  channel-vs-DM workflow and attempt to pin it in the channel.
- `scripts/setup_telegram_workspace.py` can discover the forum group, create
  the standard topics, write ignored env values, generate Telegram avatars,
  set chat/bot photos, and pin forum help.
- Audit coverage verifies a full dynamic session completes and sets
  `completed_at`.
- `/today` now uses the user's configured timezone for `target_date_local`.
- If the user approves a new active LessonPlan after an older 7-step session
  already exists for the day, `/today` supersedes the stale session and serves
  the current lesson-plan micro-drills.
- Practice headers include the LessonPlan title when available, plus mode,
  topic, goal, focus, and "why now" selection rationale.
- The current Telegram flow supports `/skip` and an inline `Skip / show answer`
  button; skipped attempts count in the dynamic session summary.
- Explicit lesson starts create a fresh `PracticeSession` from the selected
  `LessonPlan`; if a different session is already in progress, it is marked
  `superseded` only because the user chose a new lesson/mode.
- Telegram prompt and feedback rendering now uses HTML parse mode: bold
  step/stage headers, labeled Focus/Task/Target lines, and compact teacher
  feedback sections while preserving the existing buttons.
