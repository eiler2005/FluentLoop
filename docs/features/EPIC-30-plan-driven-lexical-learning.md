# EPIC-30 — New words and expressions inside Study

**Status:** Done — implemented and locally verified

**PRD references:** §6 P1, §14 Words and expressions in the personal programme

**ADR:** [ADR-0017](../adr/0017-plan-driven-lexical-learning.md)

## Scope

Extend the existing manual Study stream with a configurable lexical share and
a reviewed sense-level bank for client-facing, business, technology and general
English. Preserve the personal programme and its evidence gates.

## Acceptance

- Research and a readable editable lexical programme explain coverage and limits.
- The initial bank covers 16 functions, including general-English contexts, with
  meaning, grammar frame, register, examples and source attribution.
- Real Study selection follows 30% general / 40% workplace / 30% lexical;
  legacy plans remain compatible and retain their original allocation.
- New expressions receive teaching feedback and spaced retrieval; neither
  unseen choices nor recognition is presented as productive mastery.
- Optional independently authored guided writing, progress, issue reporting and session results
  remain isolated per learner and resumable across restarts.
- Telegram/editor controls, documentation, meaningful regression tests, CI and
  safe deployed smoke reflect the implementation.

## Delivered and verified

- Astra research: 34 primary sources and an independent sample audit of
  32 senses covering all 16 functions. The sample passed meaning/answer-key
  review; it does not independently validate all 240 entries or calibrate CEFR.
- Public bank: 240 senses (180 work, 60 general), 480 recognition questions
  and 480 writing situations; 20 introductory-C1 tasks add audience,
  uncertainty and trade-off constraints. Meanings, register, grammar and
  plain alternatives are available in a searchable offline catalog.
- Real stream tests produce 18 general / 24 work / 18 lexical answers out
  of 60. Legacy plans, changed cohorts, pauses, spacing, source rotation,
  foreign/duplicate callbacks, immutable resume and familiar exclusions pass.
- Independent application means a new learner-authored response using the
  supplied expression. It is not uncued retrieval. Genuine evaluation,
  target form/sense and spaced distinct tasks are required; copies, reused
  answers, model rewrites and fallback feedback cannot establish the milestone.
- Full local gate: **771 tests passed**, Ruff and generated-view freshness
  passed. Desktop/mobile editor tests cover the three shares, atomic rejection,
  legacy import, JSON round-trip and catalog filtering. Wheel assets and app
  imports passed; both updated green diagrams passed skill checks and visual QA.
- Configured live AI checked three authored samples: appropriate target use
  was correct, wrong-sense use partial, and off-topic writing incorrect.
  No learner answers were used or persisted.
- Exact-commit CI and production smoke follow
  [the release runbook](../runbooks/lexical-learning.md): consistent backup,
  explicit owner-only 30/40/30 activation, healthy runtime and rollback of
  artificial attempts while preserving all profiles, evidence and pending work.
