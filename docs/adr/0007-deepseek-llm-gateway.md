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
  `DEEPSEEK_TIMEOUT_SECONDS`, `DEEPSEEK_MAX_RETRIES`.
- Default model: `deepseek-v4-flash`.
- Require JSON-only responses for structured tasks and validate with Pydantic.
- Retry transient failures and return deterministic fallback where available.
- Keep the existing `AIProvider` interface so current bot flows can select
  `AI_PROVIDER=stub`, `openai`, or `deepseek`.

## Consequences

- DeepSeek calls are centralized and auditable.
- Existing OpenAI/stub paths remain available during rollout.
- Provider failures do not crash `/today`, upload approval, or answer checking.
- Future AI exercise generation must call this gateway rather than creating
  direct provider clients in feature modules.

