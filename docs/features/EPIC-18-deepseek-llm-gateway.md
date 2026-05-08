# EPIC-18 — DeepSeek LLM Gateway v1

**Status:** Planned
**PRD references:** §25.1, §25.2, §25.3
**Depends on:** EPIC-17
**Blocks:** EPIC-19

## Goal

Centralize model orchestration through a lightweight DeepSeek API gateway so
business logic does not call provider APIs directly.

## In scope

- Add a small `fluentloop.llm` package with tasks, schemas, prompts, and a
  gateway/router.
- Use DeepSeek's OpenAI-compatible API with configurable environment:
  `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_CHAT_MODEL`,
  `DEEPSEEK_TIMEOUT_SECONDS`, and `DEEPSEEK_MAX_RETRIES`.
- Support JSON tasks for material extraction, seed lesson plans, exercise
  generation, answer checking, grammar explanations, and tone feedback.
- Validate JSON responses with Pydantic, retry transient errors, and fall back
  deterministically when the provider fails.

## Out of scope

- Replacing every existing OpenAI/stub provider call in one sweep.
- LangChain, external vector DBs, voice, or web UI.

## Acceptance criteria

- DeepSeek calls are centralized and model/base URL are configurable.
- Invalid or failed LLM responses do not crash practice flow.
- Deterministic fallback works without API access.
- Docs and env templates mention the new variables without secrets.

## Verification plan

- Unit tests for task routing, model selection, JSON validation, retry/fallback,
  and mocked gateway usage.
- Live smoke: confirm `DEEPSEEK_API_KEY` exists, run a safe JSON task, verify
  fallback behavior if practical, run `/today`, and check logs for provider
  errors or secret leakage.

