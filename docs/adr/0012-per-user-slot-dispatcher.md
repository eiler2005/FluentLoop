# ADR-0012 — Per-user slot dispatcher for the daily vocabulary loop

**Status:** Accepted
**Date:** 2026-08-17
**Deciders:** Denis Ermilov
**Amends:** ADR-0004

## Context

EPIC-25 sends three short messages a day — morning cards, a midday drill, an
evening quiz — each at a time the learner chooses, in the learner's own
timezone.

The existing scheduler (`build_scheduler`) registers four APScheduler cron jobs
bound to one global timezone, `pytz.timezone(settings.timezone)`. Each job then
loops over all users inside a single firing.

Two things were wrong with the ground this had to be built on:

1. `User.timezone` and `User.reminder_time` were stored and validated but never
   read by the scheduler. `User.timezone` was used in exactly one place,
   `practice._local_date`.
2. Because of that, `send_reminders` and `run_pre_generation` computed "today"
   and "tomorrow" from `datetime.now(UTC).date()`, while
   `PracticeSession.target_date_local` is written in the user's timezone. For
   any non-UTC learner these disagree, so the reminder could fire during an
   active session.

ADR-0004 describes overnight pre-generation as running "at 03:00 user TZ". The
code never honoured that; it ran at 03:00 server time for everyone. This ADR
records the discrepancy and fixes it.

## Decision

Add one cron job, `vocab_loop_tick`, firing every minute, and resolve slot
timing per user inside the job.

- `vocab_loop.local_now(user)` converts the current instant with
  `ZoneInfo(user.timezone)`, falling back to UTC for an unknown zone.
- `vocab_loop.due_slots(prefs, now_local)` returns the slots whose delivery
  window contains the local time. The window is the slot time plus
  `CATCHUP_MINUTES = 90`, so a bot restarted at 08:20 still sends the morning
  cards and one restarted at 10:00 does not.
- Before sending, the tick INSERTs a `vocab_deliveries` row. The unique
  constraint on `(user_id, local_date, slot, seq)` is the lock: a second tick
  hits `IntegrityError`, rolls back, and skips.
- A slot that raises is marked `failed` rather than left `claimed`, so a broken
  slot is logged once instead of retried every minute.
- Cost per tick is one `select(User)`. Everything after that is pure Python
  until a slot actually matches, so no per-user query runs on a quiet minute.

Alongside this, the four existing jobs are corrected:

- `send_reminders` and `run_pre_generation` now compute dates with
  `vocab_loop.local_date(user)`, matching `practice._local_date`.
- `daily_reminder` and `weekly_summary` are registered as coroutine functions
  with `args=[...]` instead of `lambda: asyncio.create_task(...)`. The lambda
  form never held a reference to the created task, so CPython could garbage
  collect it mid-flight, exceptions vanished, and `misfire_grace_time` and
  `max_instances` measured the lambda rather than the coroutine.

## Consequences

**Positive**

- Slot times are per user and per timezone, which makes `User.timezone`
  load-bearing for the first time.
- Restart-safety, overlapping-tick safety, and the repeated hour at the end of
  DST are all handled by one unique constraint rather than three mechanisms.
- Spring-forward's skipped hour is covered by the 90-minute catch-up window.

**Negative**

- A job now runs 1440 times a day instead of once. At the current
  single-tenant scale one indexed `SELECT` per minute is negligible, but a
  large user base would need bucketing by `(timezone, slot_time)`.
- `vocab_deliveries` grows by up to three rows per user per day. It is a log
  and will eventually want pruning.

**Neutral**

- `misfire_grace_time=120`, `coalesce=True`, and `max_instances=1` mean a
  paused process resumes with a single catch-up firing rather than a burst.

## Alternatives considered

- **One cron job per user per slot.** Rejected: APScheduler's jobstore is
  in-process and non-persistent, so every job would need re-registering on
  boot and rescheduling on every `/settings` change.
- **Three global cron jobs at fixed hours.** Rejected: it repeats exactly the
  bug this ADR fixes — correct only for learners in the server's timezone.
- **A `last_sent_at` timestamp column instead of delivery rows.** Rejected: a
  timestamp cannot express "this slot was attempted and failed", and it offers
  no place to hang the poll id the quiz needs.
