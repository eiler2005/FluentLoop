# EPIC-09 — Exercise types

**Status:** Planned
**PRD references:** §15.1–15.6, §27 (example UX)
**Depends on:** EPIC-05
**Blocks:** EPIC-07 (consumes the type registry), EPIC-10

## Goal

Implement the six exercise types from PRD §15 as a registered set of
renderers and answer-shape definitions. Each type knows how to be rendered
in Telegram and what shape of answer to expect. EPIC-07 picks types when
composing a session; EPIC-10 checks answers.

## In scope

- Six exercise types from PRD §15:
  1. **Guess word/expression** — bot gives a definition, user produces
     the term.
  2. **Translate phrase** — RU → EN translation.
  3. **Cloze** — fill the gap in a sentence.
  4. **Grammar rewrite** — rewrite a sentence in a more diplomatic /
     business style (or apply a specific transformation).
  5. **Error correction** — find and fix the error in a sentence.
  6. **Business/IT follow-up** — produce a short response to a workplace
     prompt, optionally requiring specific expressions.
- A type registry: `EXERCISE_TYPES = {"guess": GuessExercise, ...}`.
- Per-type rendering: prompt format, optional hint, what user sees in
  Telegram (plain text vs inline buttons for short choices).
- Per-type answer shape: free text vs inline-button choice; expected
  answer field semantics.
- For each type, a `pretty_name` and `target_item_kinds` (e.g. cloze
  prefers `expression` and `word`, rewrite prefers `grammar_rule`).

## Out of scope

- Custom user-defined exercise types — defer.
- Multimedia (images, audio) — PRD §6 P2.
- Adaptive difficulty within a type — defer.

## Acceptance criteria

- Each of the six types renders a well-formed Telegram message given a
  `LearningItem` and AI-generated parameters.
- Each type returns a typed result for EPIC-10 to consume:
  `(user_answer: str, exercise_type: str, target_item_ids: list[int])`.
- Adding a new type requires editing only the registry + a single
  type module — no surgical edits in EPIC-07 / EPIC-08 / EPIC-10.
- Examples in PRD §27 round-trip: feeding the example prompt and the
  example user answer through the renderer + checker produces the
  expected feedback shape.

## Open questions

- For "follow-up" exercises that ask for a multi-sentence response — is
  there a soft length cap? Default: ~3 sentences max suggested in the
  prompt.
- For "guess" exercises, do we accept multiple right answers (e.g.
  "push back" vs "push back on")? EPIC-10 handles this; the type just
  passes both candidates if the AI generates them.
- Should "cloze" ever have multi-blank prompts? Default: single blank
  for MVP.

## Verification plan

1. For each type, generate one exercise from a seeded `LearningItem`
   and visually inspect the rendering in Telegram.
2. Type registry test: `len(EXERCISE_TYPES) == 6` and every entry has
   `render` and `parse_answer` callable attributes.
3. Re-run PRD §27 example through the pipeline — expected feedback
   matches the PRD example shape.
