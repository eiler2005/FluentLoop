# EPIC-06 — Spaced repetition

**Status:** Planned
**PRD references:** §12, §24 (`ReviewState`)
**Depends on:** EPIC-05
**Blocks:** EPIC-07

## Goal

Every `LearningItem` (word / expression / grammar rule / mistake pattern)
gets a `ReviewState` and a `next_review_at` timestamp. A simple interval
algorithm advances the schedule based on the four-button result
(Again / Hard / Good / Easy). The result is provided by EPIC-10's answer
checker (with optional user override), but this epic only cares about
the bookkeeping.

## In scope

- `ReviewState` table per PRD §24: `id`, `learning_item_id`, `due_at`,
  `last_reviewed_at`, `review_count`, `success_count`, `fail_count`,
  `difficulty`, `stability`, `last_result`, timestamps.
- Algorithm — keep it simple per PRD §12:
  - `Again` → `due_at = now`, `difficulty += 1`, `fail_count += 1`.
  - `Hard`  → `due_at = now + 1d`, `difficulty += 0.5`, `fail_count += 1`.
  - `Good`  → `due_at = now + min(7d, max(2d, last_interval × 2.0))`,
              `success_count += 1`.
  - `Easy`  → `due_at = now + max(7d, last_interval × 3.0)`,
              `success_count += 1`.
- `due_at` is queryable: "items due in the next 24 hours, ordered by
  priority".
- Priority signal exposed for EPIC-07: `is_overdue`, `is_weak`
  (`fail_count > success_count` over last N reviews), `is_due_soon`.
- Helper functions to mark a result and advance the state, decoupled from
  the Telegram layer (so EPIC-10 can call them cleanly).

## Out of scope

- FSRS / SM-2 / proper open-source SR algorithm — PRD §12 explicitly says
  simple intervals are enough for MVP. Upgrade is a P1 enhancement.
- Per-tag scheduling — PRD has no such requirement.
- Lapses-as-leeches behavior (auto-suspend after N failures) — defer.

## Acceptance criteria

- Adding a `LearningItem` creates a `ReviewState` with `due_at = now`
  (i.e. the item is immediately reviewable).
- `record_result(item_id, "Good")` updates `last_result`, advances
  `due_at`, and increments `success_count` and `review_count`.
- After three consecutive `Good` results, `due_at` is at least 7 days
  out from the latest review.
- `record_result(item_id, "Again")` resets `due_at` to ~now.
- `get_due_items(user_id, limit)` returns items in priority order
  (overdue → due-now → due-soon).

## Open questions

- Initial interval after first ever review: 1 day or 3 days for "Good"?
  Default: 2 days (matches the `max(2d, …)` floor in the algorithm above).
- Where does the algorithm live? Default: `src/fluentloop/srs.py`, pure
  functions, no DB dependency — DB layer calls in.

## Verification plan

1. Add 5 learning items.
2. Mark them all `Good` once; assert `due_at` is ~2 days out.
3. Mark them all `Good` again at the simulated due date; assert
   `due_at` is now ~4 days out.
4. Mark one `Again`; assert `due_at` is ~now.
5. `get_due_items` orders correctly.
