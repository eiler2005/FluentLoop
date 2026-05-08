# ADR-0003 — AI provider and model tiering

**Status:** Accepted
**Date:** 2026-05-06
**Deciders:** Denis Ermilov

## Context

FluentLoop makes many LLM calls per active week. Rough back-of-envelope:

- **Extraction** (PRD §25.1): 1–3 calls per uploaded lesson, ~4 lessons/week
  → ~5–10 calls/week.
- **Exercise generation** (PRD §25.2): the original MVP estimated
  7 exercises × 4 active days/week → ~28 calls/week. The current
  Learning Engine uses 15-20 micro-drills, but only high-value stages should
  call an LLM; simple drills stay deterministic.
- **Answer checking** (PRD §25.3): 15-20 attempts × 4 active days/week, usually
  routed to the fast profile.
- **Weekly report** (PRD §19): 1 call/week.

Total: ~70–80 LLM calls per active week, before retries / regenerations.

A single top-tier model on every call burns budget. A single cheap model
risks bad B2+/C1 judgment calls — the difference between "wrong" and
"stylistically subpar" is subtle, and bad feedback compounds when it trains
future practice.

## Decision

Use **OpenAI** with a two-tier strategy:

| Tier | Model | Used for |
|---|---|---|
| **Light** | `gpt-4o-mini` | Routine answer checking (cloze, exact-match, simple translation), exercise prompt rendering, simple classification (mistake type tag). |
| **Heavy** | `gpt-4o` | Extraction from raw materials, grammar feedback with explanation, "more natural" rephrasings, weekly report, mistake-pattern detection. |

The provider is set via env: `AI_PROVIDER=openai`, with model names in env
(`OPENAI_MODEL_LIGHT=gpt-4o-mini`, `OPENAI_MODEL_HEAVY=gpt-4o`) so they can
be tuned without code changes.

**2026-05-08 roadmap update:** ADR-0007 adds DeepSeek as the learning-engine
provider behind the same abstraction. ADR-0003 remains the original MVP
provider/cost decision; ADR-0007 owns DeepSeek task routing and fallback.

## Alternatives considered

- **Anthropic (Haiku 4.5 + Sonnet 4.6).** Strong at B2+/C1 nuance,
  excellent prompt caching, fits the user's existing Claude tooling.
  Heavy-tier price per 1M tokens is currently higher than `gpt-4o`.
  Rejected on cost-per-call for this single-user budget.
- **Single heavy model (gpt-4o everywhere).** Simpler. Rejected on
  cost — unnecessary for cloze/exact-match.
- **Single light model (gpt-4o-mini everywhere).** Cheaper. Rejected
  because subtle stylistic / hedging / collocation feedback at B2+ level
  benefits measurably from the heavy tier.
- **Both providers behind an abstraction from day 1.** Defers the
  decision but doubles the surface to test. Rejected for MVP — pick one,
  ship faster, switch later if needed.
- **Local model (Llama, Qwen) on the VPS.** Zero per-call cost and best
  privacy. Rejected for MVP — VPS RAM pressure, model quality at this
  level needs bigger weights than a personal-tier VPS hosts comfortably.

## Consequences

**Positive:**

- Predictable cost envelope (gpt-4o-mini pricing dominates the call
  count; gpt-4o is reserved for the ~30% of calls where quality matters).
- OpenAI's Python SDK is mature, well-documented, and structured-output
  support (`response_format=json_schema`) simplifies validation.
- Easy A/B against a future Anthropic tier later — the abstraction layer
  is the same shape.

**Negative:**

- Lesson notes, mistakes, and answers go to OpenAI. Privacy disclosure
  in [`../../SECURITY.md`](../../SECURITY.md) covers this. Optional
  redaction list mitigation captured as P1.
- Need a thin abstraction (`src/fluentloop/ai/provider.py`) that picks
  light vs heavy per *task type*, not per call site. Without that
  abstraction, tier choices leak across the codebase.
- Cost telemetry from day 1 — log token counts per call, sum per week.
  Without this, the budget assumption is unverifiable.

**Follow-ups:**

- Add `openai>=1.40.0` to `requirements.txt` in EPIC-01.
- Implement `src/fluentloop/ai/provider.py` with `light_call()` /
  `heavy_call()` entrypoints, both returning Pydantic-validated results.
- Add `usage_log` table or simple JSONL log for per-call token counts.
- Re-evaluate after 4 weeks: if cost is comfortable, consider trying
  Anthropic Sonnet on the heavy tier for grammar feedback and compare
  output quality side-by-side.

## References

- PRD §25 (AI requirements)
- [`../architecture.md`](../architecture.md) §3
- [`../../.env.example`](../../.env.example)
- [`../../SECURITY.md`](../../SECURITY.md)
- `docs/features/EPIC-04-ai-extraction-and-approval.md`
- `docs/features/EPIC-10-answer-checking-feedback.md`
- OpenAI structured outputs: https://platform.openai.com/docs/guides/structured-outputs
