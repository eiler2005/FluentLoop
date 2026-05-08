# ADR-0004 — Exercise pre-generation strategy

**Status:** Accepted
**Date:** 2026-05-06
**Deciders:** Denis Ermilov

## Context

A daily session was originally scoped as 7 exercises (PRD §14). The current
Learning Engine expands that into 15-20 micro-drills inside the same
15-minute lesson, which makes the latency concern even stronger if every
exercise were generated on demand. Pre-generation and deterministic fallbacks
keep the first prompt fast.

Pre-generation moves the cost off the user-visible path.

## Decision

Pre-generate the day's session in an **overnight batch at 03:00 user TZ**
via APScheduler (in-process — see [`../architecture.md`](../architecture.md)
§5).

Workflow:

1. APScheduler `cron` trigger fires `compose_tomorrow_session` at 03:00
   in the user's timezone (`User.timezone`).
2. The job queries spaced-repetition state, mistake patterns, favorites,
   active lesson plans, material context, and recent uploads, and selects a
   dynamic target set per `EPIC-07`/`EPIC-16` priority rules.
3. For each target it generates `(prompt, expected_answer, hint,
   explanation, exercise_type)` via the AI heavy/light tier from
   ADR-0003.
4. Results are stored in a `practice_session_cached` row keyed by
   `(user_id, target_date_local)`.
5. When the user fires `/today` or the reminder triggers, the bot serves
   the cached row instantly. **Answer checking remains real-time** — that
   *needs* to look at the actual user input.

**Cache invalidation rule:** if the user uploads new material between
03:00 and the practice session, EPIC-07 may inject 1–2 fresh exercises on
top of the cached batch. Full re-generation on every upload is overkill.

**Fallback:** if pre-gen failed (AI down, rate limit, container restart),
firing `/today` triggers on-demand generation with a "preparing
exercises…" message. The fallback is acceptable because it's rare; the
cache is the happy path.

## Alternatives considered

- **Pure on-demand generation.** Always uses freshest state. Rejected on
  UX grounds — 25–35s wait kills "15 min daily".
- **Generate at reminder time, then deliver.** Closer to real-time
  state, but the user still waits ~30s after the reminder. Rejected.
- **Pre-generate the whole week.** Minimal AI traffic. Rejected because
  state drift is large — Wednesday's session generated Sunday night
  misses Monday's mistakes.
- **Pre-gen 1 hour before reminder time.** Adapts to user TZ but the
  window is tight; if AI lags, the user sees "preparing…" anyway.
  03:00 is far enough that retries don't blow the schedule.

## Consequences

**Positive:**

- User-visible session start is instant (cache hit).
- Failures are detected hours before the user notices and can be
  retried.
- Telemetry: cache hit / miss rate is a clean product metric.

**Negative:**

- Need a `practice_session_cached` table — schema change owned by
  EPIC-07.
- APScheduler config must be visible in env (`PRE_GEN_HOUR=3`,
  `PRE_GEN_MINUTE=0`) so the time can be tuned without code changes.
- Slight staleness if the user changes settings (level, focus areas)
  between pre-gen and morning. Acceptable.

**Follow-ups:**

- EPIC-07: implement the `practice_session_cached` schema, the
  composer, and the AI generation calls.
- EPIC-08: implement the cache-hit serving path and the on-demand
  fallback.
- Add `PRE_GEN_HOUR` / `PRE_GEN_MINUTE` to `.env.example`.

## References

- PRD §13, §14
- [`../architecture.md`](../architecture.md) §4, §5
- `docs/features/EPIC-07-automatic-practice-generation.md`
- `docs/features/EPIC-08-daily-practice-telegram.md`
