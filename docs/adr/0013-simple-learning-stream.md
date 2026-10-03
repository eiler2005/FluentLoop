# ADR-0013 — Manual simple learning stream

**Status:** Accepted
**Date:** 2026-10-03
**Deciders:** Denis Ermilov
**Amends:** ADR-0012 (per-profile scheduling)

## Context

The owner wants a simpler primary learning entrance for a personal pilot:
continuous button questions, mixed phrases and grammar, no notifications, and
optional writing after stopping. Existing full lessons and admitted users'
content/progress must remain available. A daily vocabulary quiz is grouped by
local date and slot, while a stream can cross dates and restart several times
on the same day.

## Decision

Use the existing `PracticeSession` and `PracticeAttempt` tables, with dedicated
`simple_active` and `simple_bonus` states. A stream keeps one pending question
snapshot in its exercises JSON; attempts retain answered-question history.
Each snapshot has a monotonically increasing index and a content fingerprint
independent of option ordering. Stopping completes the run but preserves the
last displayed snapshot. Resume does not depend on the local date.

An owner/status/index conditional database update claims each answer inside the
same transaction as the attempt, SRS change, and next snapshot. Duplicate,
stale, and foreign callbacks cannot advance progress. Starting also serializes
on the existing user row before checking for an active stream. No schema
migration or unbounded exercises array is needed. Legacy staged composition,
lesson-cache invalidation, and GIR appenders do not operate on these states.

Keep the existing global SRS. Successful simple recognition has an additional
24-hour per-question eligibility floor, derived from normal-mode attempts.
Incorrect questions require five intervening other answers before reappearing.
Explicit early familiar practice records recognition but does not advance SRS
on a correct answer. Incorrect answers may reset it. Recognition never invokes
automatic graduation. Writing is a separate one-exercise run linked to its
completed parent and tagged as production; outcome metrics exclude recognition.
Genuine written feedback uses the existing mistake-event/pattern loop inside
the same claim transaction. Grammar bonuses ask for the structure in a new
situation; phrase bonuses use the curated chunk. Skipping creates no failure.

The profile setting is `preferences_json["learning"]["mode"]`, defaulting to
`advanced`. Only an explicitly selected pilot profile changes to `simple`.
Schedulers skip simple profiles for reminders, vocabulary pushes, preparation,
and weekly summaries. Explicit advanced commands continue to work.
The optional writing capture uses persisted chat/user/topic state and bonus ID.
Read-only navigation
preserves it; starting another answer-taking flow cancels it, and entering full
practice completes an open simple stream. Actual Telegram sender identity gates
simple-profile interactions in a forum; legacy owner routing is not authentication.

Reviewed source questions live in item metadata alongside immutable provenance.
Only approved personal copies are selected; imported phrase pairs use explicit
meaning/context rather than blindly grading two valid alternatives.

## Consequences

- A single manual entrance requires no learner decisions about lesson formats.
- Persisted snapshots survive restarts and preserve answer-button meaning.
- Small banks can produce a short stream and an honest exhaustion result.
- SRS and recognition/production evidence remain separate without a new engine.
- Attempts grow with answered questions, while pending-run JSON remains bounded.
- The import requires contextual QA; an unreviewed wrong/right pair is not a quiz.
- Native vocabulary poll delivery retains its existing daily-row contract.
