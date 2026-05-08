# EPIC-20 — Grammar Brain v1

**Status:** Planned
**PRD references:** §11, §17, §18, §22.4
**Depends on:** EPIC-19
**Blocks:** EPIC-21

## Goal

Represent grammar as trainable business/IT communication skills that can be
selected by the Learning Engine and connected to mistakes and items.

## In scope

- Seed or expand practical concepts such as articles with project events,
  hedging recommendations, diplomatic disagreement, modal verbs for
  suggestions, business prepositions, countable/uncountable business nouns,
  conditionals for risks, and register/tone.
- Let grammar or mistake focus stages use relevant `GrammarConcept` rows.
- Keep explanations short, practical, and Telegram-friendly.
- Use business/IT examples by default.

## Out of scope

- A full grammar curriculum.
- Complex graph visualization.
- Multi-user personalization.

## Acceptance criteria

- At least 8-10 useful B2+/C1 business/IT concepts exist.
- Grammar concepts appear in daily practice.
- Linked mistake patterns can influence grammar focus.
- Existing SRS and learning-item behavior remains unchanged.

## Verification plan

- Unit tests for seed concepts, concept graph links, grammar selection, and a
  mistake pattern influencing grammar focus.
- Live smoke: verify seeded concepts, create or use a relevant mistake
  pattern, run `/today`, answer grammar focus, verify feedback/SRS, and check
  logs.

