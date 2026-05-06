# EPIC-12 — Grammar rules graph

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §11, §18, §22.4
**Depends on:** EPIC-05, EPIC-11
**Blocks:** EPIC-07 (uses parent-concept walks)

## Goal

Grammar rules are not a flat list — they are concepts with parent / child
relationships. When a user repeatedly fails a narrow concept (e.g.
"hedging recommendations"), the bot can occasionally surface a parent
concept (e.g. "modal verbs for recommendations") to repair the
foundation.

## In scope

- `GrammarConcept` table per PRD §24: `id`, `title`, `description`,
  `parent_ids` (JSON list), `child_ids` (JSON list), `examples` (JSON
  list), timestamps.
- Bidirectional consistency: writing a parent_id on concept A also
  appends A to parent's `child_ids`, transactionally.
- `LearningItem(type=grammar_rule)` rows can link to a `GrammarConcept`
  via `linked_grammar_concept_id` (already exists in
  `MistakeEvent` / `MistakePattern`).
- Walk helpers: `parents_of(concept_id, depth=N)`,
  `children_of(concept_id, depth=N)`.
- Selection logic for EPIC-07: when a high-confidence mistake pattern
  links to a `GrammarConcept`, EPIC-07 may sample one parent concept
  (with low probability — e.g. 15%) for an additional refresher
  exercise.
- `/rules` command: list grammar concepts the user has touched, with
  weak ones highlighted.
- Seed set: ship 10–15 starter concepts from PRD §18 (articles, modal
  verbs, conditionals, reported speech, etc.) so the graph isn't empty
  on day one.

## Out of scope

- Full grammar curriculum — the bot is a consolidation tool, not a
  course.
- Auto-induction of new concepts from text — too noisy; user / teacher
  drives this.
- Graph visualization in the bot — deferred to EPIC-15 (web UI) if
  ever.
- Cycle detection beyond a one-step check — assume the user / seed set
  doesn't create cycles.

## Acceptance criteria

- Seed concepts load on first run if `grammar_concepts` is empty.
- Adding a parent link from concept A to concept B also adds A as a
  child of B (and vice versa for unlink).
- `parents_of("hedging recommendations", depth=2)` returns at least
  `modal verbs for recommendations` and (via that) `modal verbs`.
- EPIC-07 includes a parent-concept refresher in ~15% of sessions
  where a child concept has a high-confidence mistake pattern.
- `/rules` shows seeded concepts plus any user-attached learning items
  with their pattern counts.

## Open questions

- Where do seed concepts live? Default: `src/fluentloop/seeds/grammar_
  concepts.yml`, loaded on app start with idempotent insert.
- Probability tuning for parent-concept refresher (15% is a guess) —
  revisit after 4 weeks.
- Should "weak" be defined per concept (aggregate of mistake events
  linked to it) or per linked `LearningItem`? Default: aggregate of
  events at the concept level.

## Verification plan

1. Fresh DB → start bot → assert ~12 `grammar_concepts` rows from seed.
2. Link a `MistakeEvent` to "hedging recommendations"; promote to a
   `confidence=high` pattern.
3. Run pre-gen 20 times; assert ~3 sessions include a "modal verbs for
   recommendations" or "modal verbs" exercise.
4. `/rules` lists concepts; the hedging one is highlighted as weak.

## Notes from implementation

- Added seeded grammar concepts, bidirectional parent links, parent/child walk
  helpers, and `/rules` rendering.
