# ADR-0007 — DeepSeek LLM gateway for learning engine roadmap

**Status:** Accepted
**Date:** 2026-05-08
**Deciders:** Denis Ermilov

## Context

EPIC-16 through EPIC-21 add lesson plans, contextual exercise generation, and
grammar/mistake explanations. These tasks need structured JSON from a chat
model, but FluentLoop must stay small: one Docker container, SQLite, local
storage, no LangChain, and deterministic fallback.

ADR-0003 selected OpenAI for the initial MVP. The learning-engine roadmap now
selects DeepSeek as the primary provider for upcoming model-orchestration work.

## Decision

Add a small internal DeepSeek gateway under `src/fluentloop/llm/`.

- Use DeepSeek's OpenAI-compatible chat API.
- Configure through env:
  `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_CHAT_MODEL`,
  `DEEPSEEK_FAST_MODEL`, `DEEPSEEK_PLANNER_MODEL`,
  `DEEPSEEK_EXTRACTOR_MODEL`, `DEEPSEEK_PLANNER_REASONING_EFFORT`,
  `DEEPSEEK_TIMEOUT_SECONDS`, `DEEPSEEK_MAX_RETRIES`.
- Default fast model: `deepseek-v4-flash`.
- Default teacher planner/extractor model: `deepseek-v4-pro`.
- Keep `DEEPSEEK_CHAT_MODEL` as a backward-compatible fallback.
- Require JSON-only responses for structured tasks and validate with Pydantic.
- Retry transient failures and return deterministic fallback where available.
- For material extraction and lesson planning, route planner/extractor profile
  first, fast profile second, deterministic fallback third.
- Disable provider SDK hidden retries and keep retry/backoff policy in the
  FluentLoop gateway.
- Keep the existing `AIProvider` interface so current bot flows can select
  `AI_PROVIDER=stub`, `openai`, or `deepseek`.

## Consequences

- DeepSeek calls are centralized and auditable.
- Existing OpenAI/stub paths remain available during rollout.
- Provider failures do not crash `/today`, upload approval, or answer checking.
- Planning-quality tasks can use a stronger profile without making every
  high-frequency answer check expensive or slow.
- A slow planner model can still make upload extraction take tens of seconds,
  but the fast-profile fallback keeps the user flow recoverable.
- The compact extraction prompt and full candidate preview make it easier to
  inspect what will be approved before the lesson pool is created.
- Future AI exercise generation must call this gateway rather than creating
  direct provider clients in feature modules.
