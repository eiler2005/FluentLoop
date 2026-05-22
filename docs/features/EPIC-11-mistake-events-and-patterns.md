# EPIC-11 — Mistake events and mistake patterns

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §17, §22.3, §24 (`MistakeEvent`, `MistakePattern`)
**Depends on:** EPIC-10 (writes `MistakeEvent`s)
**Blocks:** EPIC-07 (consumes high-confidence patterns), EPIC-12

## Goal

Turn individual mistakes into long-term training material. Every meaningful
error becomes a `MistakeEvent`. When similar events accumulate, a
`MistakePattern` is created — but conservatively: only patterns the user
has explicitly confirmed influence future practice aggressively. Low-
confidence patterns sit in a "candidate" state where they're visible but
not yet driving exercise generation.

## In scope

- `MistakeEvent` table per PRD §24: `id`, `user_id`, `wrong_answer`,
  `corrected_answer`, `explanation`, `mistake_type`, `linked_learning_
  item_id`, `linked_grammar_concept_id`, `created_at`.
- `MistakePattern` table per PRD §24, plus a `confidence` enum:
  `low` (auto-created from clustering, not yet user-confirmed) and
  `high` (user-confirmed via inline button).
- **Concrete detection threshold:** ≥3 similar `MistakeEvent` rows
  within a rolling 14-day window → auto-create a `MistakePattern` with
  `confidence=low`. "Similar" = same `mistake_type` AND
  (same `linked_grammar_concept_id` OR same `linked_learning_item_id`).
- Pattern promotion: when a `low` pattern is created, the bot sends a
  one-time message: "I noticed a recurring mistake: <description>. Want
  me to focus on this?" `[Yes, focus on it]` `[No, ignore]`
  `[Show me examples]`. `Yes` promotes to `high`; `No` archives the
  pattern; `Show examples` lists the underlying `MistakeEvent`s.
- Only `confidence=high` patterns are sampled aggressively by EPIC-07.
- `low` patterns are visible via `/mistakes` but don't drive generation.
- `/mistakes` command: list active patterns with confidence and event
  count.
- Pattern update: each new matching `MistakeEvent` appended to the
  pattern's `wrong_examples`; corrections appended to `correct_examples`.

## Out of scope

- Cross-user pattern detection — mistake patterns stay per user; shared
  aggregate insights would need a separate privacy review.
- Auto-archiving stale patterns (no events in 60 days) — P1
  enhancement.
- Pattern → grammar concept inference (suggesting that a mistake
  pattern might belong to a not-yet-tagged concept) — defer to EPIC-12.
- Importing mistake history from outside the bot — defer.

## Acceptance criteria

- A new `MistakeEvent` is created whenever EPIC-10's logic decides
  `should_create_mistake_event=true` AND the user did not dispute the
  AI verdict.
- Three similar events within 14 days create exactly one
  `confidence=low` pattern (not three).
- On creation, the pattern-promotion prompt is sent within the next
  feedback message (not interrupting an in-progress exercise).
- `[Yes, focus on it]` promotes confidence to `high`; the pattern starts
  showing up in EPIC-07 sessions.
- `[No, ignore]` sets `status=archived` on the pattern; future events
  do **not** re-create it (the events still log, but no new pattern row).
- `/mistakes` shows all `active` patterns with their counts and
  confidence.

## Open questions

- "Similar" threshold may be too strict (same type + same item) or too
  loose (same type only). Default uses the AND form; revisit after
  4 weeks of real data.
- Should the user be able to demote a `high` pattern back to `low` /
  archive it? Default: yes, via `/mistakes` → tap pattern →
  `[Stop focusing]`.
- What if the AI's `mistake_type` is wrong? The dispute flow from
  EPIC-10 already prevents the event from being created at all — that's
  the right place to stop bad data, not here.

## Verification plan

1. Seed 3 `MistakeEvent` rows with the same `mistake_type` and same
   `linked_grammar_concept_id`, dated within 14 days.
2. Verify exactly one `MistakePattern(confidence=low)` is created on
   the third insert.
3. The promotion prompt appears in the next feedback message; tap
   `[Yes]`; pattern's confidence flips to `high`.
4. Run EPIC-07 pre-gen; verify the pattern surfaces as a "mistake-based
   exercise" in the session.
5. Add a fourth matching `MistakeEvent`; verify the pattern's
   `wrong_examples` grows by 1, no new pattern row created.
6. `/mistakes` lists the pattern with count and confidence.

## Notes from implementation

- Implemented mistake-event ingestion, the ≥3 similar events / 14-day pattern
  threshold, low-confidence creation, promotion, archive, and `/mistakes`
  rendering.
- Added `/mistakes focus <id>` and `/mistakes ignore <id>` so the user can
  promote or archive detected recurring patterns from Telegram.
- Added `/mistakes examples <id>` and inline `Focus` / `Ignore` / `Examples`
  buttons to inspect stored wrong/correct examples before deciding.
- EPIC-10 feedback now calls ingestion automatically when it creates a
  `MistakeEvent`; the feedback text points to `/mistakes focus <id>` /
  `/mistakes ignore <id>` when a recurring low-confidence pattern appears.
- Audit coverage verifies an archived pattern is not re-created by future
  matching events.
