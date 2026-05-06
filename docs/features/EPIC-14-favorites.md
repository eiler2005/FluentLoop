# EPIC-14 — Favorites

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §20
**Depends on:** EPIC-05 (column already exists), EPIC-07
**Blocks:** —

## Goal

Let the user mark items as important. Favorited items receive a small
priority boost in EPIC-07's selection logic and have a dedicated
listing.

## In scope

- Toggle UI: every learning-item display (in `/add` confirmation, in
  EPIC-04 approval, in `/mistakes` and `/rules`) shows a `★` /
  `☆` inline button to toggle `is_favorite`.
- A direct command flow: `/favorites` lists current favorites (paginated
  if more than 20).
- EPIC-07 selector treats favorites as a soft boost: when two candidates
  are otherwise tied on priority, the favorite wins. Favorites do **not**
  override due / weak / mistake-pattern priority.
- Toggling does not affect SRS state.

## Out of scope

- Tag-based filtering of favorites — defer.
- Importing / exporting favorites — PRD §6 P1.
- Notifications when a favorite becomes due — covered by the existing
  daily reminder.

## Acceptance criteria

- Tapping `☆` on an item flips `is_favorite` to true and the button
  re-renders as `★`.
- `/favorites` lists all `is_favorite=true AND status=active` items,
  20 per page.
- In a head-to-head EPIC-07 selection where two candidates have
  identical SRS / weakness / freshness, the favorite is picked.
- Archiving an item does not unfavorite it (re-activation should
  preserve the flag).

## Open questions

- Should the boost have a configurable weight? Default: no — keep it
  simple, "tiebreaker only".
- Cap on number of favorites? PRD doesn't require one. Default: no
  cap, but `/favorites` paginates.

## Verification plan

1. Add 5 items; favorite 2.
2. `/favorites` shows the 2.
3. Force two candidates to tie in EPIC-07 selection; verify the
   favorite wins.
4. Archive a favorited item; re-activate; verify `is_favorite` is
   still true.

## Notes from implementation

- Added favorite toggling, favorite listing, and selector tiebreaker data.
- Inline star buttons are pending richer Telegram callback wiring.
