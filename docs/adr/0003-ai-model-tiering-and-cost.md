# ADR-0003 — AI model tiering and cost envelope

**Status:** Proposed (stub — to be filled in before EPIC-04 / EPIC-10)
**Date:** TBD
**Deciders:** TBD

## Context

FluentLoop makes many LLM calls per active week. Rough back-of-envelope:

- **Extraction** (PRD §25.1): 1–3 calls per uploaded lesson, ~4 lessons/week
  → ~5–10 calls/week.
- **Exercise generation** (PRD §25.2): 7 exercises × 4 active days/week
  → ~28 calls/week. Pre-generation (ADR-0004) batches but doesn't reduce
  count.
- **Answer checking** (PRD §25.3): 7 attempts × 4 active days/week → ~28
  calls/week.
- **Weekly report** (PRD §19): 1 call/week.

Total: ~70–80 LLM calls per active week, before retries / regenerations.

Running everything on a top-tier model (Opus 4.7, GPT-4o) burns budget fast
for one user. Running everything on a cheap model risks bad B2+/C1- judgment
calls — the difference between "wrong" and "stylistically subpar" is subtle,
and bad feedback compounds when it trains future practice.

## Decision

TBD. Working assumption documented below for reviewers to challenge.

**Working assumption — two-tier strategy:**

| Tier | Model class | Used for |
|---|---|---|
| **Light** | Anthropic `claude-haiku-4-5` / OpenAI `gpt-4o-mini` | Routine answer checking (cloze, exact-match, simple translation), exercise prompt rendering, simple classification (mistake type tag). |
| **Heavy** | Anthropic `claude-sonnet-4-6` / OpenAI `gpt-4o` | Extraction from raw materials, grammar feedback with explanation, "more natural" rephrasings, weekly report, mistake-pattern detection. |

The provider (`AI_PROVIDER=anthropic` or `openai`) is selected via env, with
both tiers' model names also in env (see `.env.example`).

## Alternatives considered

- **Single heavy model everywhere.** Pro: highest quality, simpler. Con:
  cost; latency on every check.
- **Single light model everywhere.** Pro: cheap, fast. Con: poor judgment
  on stylistic / hedging / collocation feedback at B2+ level.
- **Local model (Llama, Qwen) on the VPS.** Pro: zero per-call cost,
  privacy. Con: VPS RAM pressure, model quality at this level requires
  bigger weights than a small VPS can host, deployment complexity.

## Consequences

- Need a thin abstraction (`src/ai/provider.py` or similar) that switches
  light/heavy per task type, not per call site.
- Need cost telemetry from day 1 — log token counts per call, sum per
  week. Without this, the budget assumption is unverifiable.
- Prompts must work across both providers. Use a JSON-schema validation
  layer (Pydantic) so model differences don't cause silent breakage.
- ADR can be revisited after 4 weeks of real usage with actual cost data.

## References

- PRD §25 (AI requirements)
- [`../architecture.md`](../architecture.md) §3
- [`../../.env.example`](../../.env.example)
- `docs/features/EPIC-04-ai-extraction-and-approval.md`
- `docs/features/EPIC-10-answer-checking-feedback.md`
