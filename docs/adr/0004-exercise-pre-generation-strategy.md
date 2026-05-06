# ADR-0004 — Exercise pre-generation strategy

**Status:** Proposed (stub — to be filled in before EPIC-07 / EPIC-08)
**Date:** TBD
**Deciders:** TBD

## Context

A daily session is 7 exercises (PRD §14). If the bot generates each exercise
on demand when the user starts the session, the user waits ~3–5 seconds per
exercise just for the AI round-trip — 25–35 seconds of waiting before they
even start, plus latency mid-session. That breaks the "15 minutes of
practice" UX.

Pre-generation moves the cost off the user-visible path.

## Decision

TBD. Working assumption documented below.

**Working assumption — overnight batch:**

1. APScheduler (in-process, see [`../architecture.md`](../architecture.md)
   §5) fires a `compose_tomorrow_session` job at a quiet local hour
   (e.g. 03:00 user TZ).
2. The job queries the spaced-repetition state, mistake patterns,
   favorites, and recent uploads, and selects ~7+ targets per
   `EPIC-07`'s priority rules.
3. For each target it generates `(prompt, expected_answer, hint,
   explanation, exercise_type)` via the AI heavy/light tier appropriate
   to the exercise.
4. Results are stored in a `practice_session_cached` row keyed by
   `(user_id, target_date)`.
5. When the user fires `/today` or the reminder triggers, the bot serves
   the cached row instantly. **Answer checking remains real-time** — that
   *needs* to look at the actual user input.

**If pre-generation fails** (AI down, rate limit), the bot falls back to
on-demand generation with a one-line message ("preparing exercises…"). The
fallback is acceptable because it's rare; the cache is the happy path.

**Cache invalidation:** if the user uploads new material between the
pre-gen run and the practice session, the bot may inject 1–2 fresh items
on top of the cached batch. Full re-generation is overkill.

## Alternatives considered

- **Pure on-demand generation.** Pro: always uses freshest state. Con:
  user-visible latency; bad UX for "15 min daily".
- **Generate at reminder time, then deliver.** Pro: closer to real-time
  state. Con: ~30s lag between reminder and first exercise.
- **Pre-generate the whole week.** Pro: minimal AI traffic. Con: state
  drift — if the user makes mistakes Mon, the Wed session was generated
  before that signal was available.

## Consequences

- Need a `practice_session_cached` table (or similar) — schema change in
  EPIC-07.
- APScheduler config must be visible in env (`PRE_GEN_HOUR=3`) so it can
  be tuned without code changes.
- Telemetry: log when a session is served from cache vs generated
  on-demand. Cache hit rate is a real product metric.
- If/when a web UI is added (deferred EPIC-15), it should NOT trigger
  on-demand generation either — same cache.

## References

- PRD §13, §14
- [`../architecture.md`](../architecture.md) §4, §5
- `docs/features/EPIC-07-automatic-practice-generation.md`
- `docs/features/EPIC-08-daily-practice-telegram.md`
