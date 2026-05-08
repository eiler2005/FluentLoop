# EPIC-19 — AI Exercise Generator v1

**Status:** Done (2026-05-08)
**PRD references:** §13, §15, §25.2
**Depends on:** EPIC-18
**Blocks:** EPIC-20, EPIC-21

## Goal

Use DeepSeek through the gateway to generate more natural business/IT exercises
where deterministic templates are too repetitive.

## In scope

- Add AI generation for high-value stages: free production, grammar or mistake
  focus, business follow-up, and richer input examples.
- Validate generated exercises against the existing exercise shape plus stage
  metadata.
- Preserve deterministic templates as fallback.
- Keep prompts concise, Telegram-friendly, and targeted at B2+/C1 business/IT
  English.

## Out of scope

- AI generation for every simple cloze or guess prompt.
- New persistent exercise queues beyond the existing session JSON.
- LangChain, external tools, voice, or web UI.

## Acceptance criteria

- Free-production and grammar/business prompts are more varied.
- AI-generated exercises include stage metadata and target item ids.
- AI failure falls back to deterministic templates.
- Feedback, SRS, and attempts still work for generated exercises.

## Verification plan

- Unit tests for successful AI generation, fallback, schema validation,
  metadata, and Learning Engine integration.
- Live smoke: verify at least one AI-generated free-production prompt and one
  grammar/business prompt, answer them, verify feedback, attempts, SRS, and
  logs.

## Notes from implementation

- Added `src/fluentloop/ai_exercises.py` as a small generator layer over the
  DeepSeek gateway.
- The Learning Engine can enhance high-value stages when a gateway is supplied:
  `grammar_or_mistake_focus` and `free_production`.
- AI-generated exercise dicts preserve the existing exercise contract and add
  `ai_generated`, tags, difficulty, and stage metadata.
- Empty or invalid model output falls back to the deterministic base exercise.
