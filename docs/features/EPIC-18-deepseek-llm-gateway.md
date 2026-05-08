# EPIC-18 — DeepSeek LLM Gateway v1

**Status:** Done (2026-05-08)
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
  `DEEPSEEK_FAST_MODEL`, `DEEPSEEK_PLANNER_MODEL`,
  `DEEPSEEK_EXTRACTOR_MODEL`, `DEEPSEEK_PLANNER_REASONING_EFFORT`,
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

## Notes from implementation

- Added `src/fluentloop/llm/` with DeepSeek client construction, task enum,
  prompts, JSON gateway, router, and shared schemas.
- Added `DeepSeekProvider` behind the existing `AIProvider` interface so
  runtime can use `AI_PROVIDER=deepseek` without changing bot call sites.
- Gateway validates Pydantic JSON, retries transient failures, logs usage, and
  supports deterministic fallback when the key is missing or calls fail.
- Added ADR-0007 and documented `DEEPSEEK_*` runtime variables.
- Added task-aware DeepSeek routing: `deepseek-v4-pro` is used for teacher
  lesson planning and lesson-note extraction, while `deepseek-v4-flash` remains
  the default for answer checks and fast exercise generation.
- Added task-specific env defaults: `DEEPSEEK_FAST_MODEL`,
  `DEEPSEEK_PLANNER_MODEL`, `DEEPSEEK_EXTRACTOR_MODEL`, and
  `DEEPSEEK_PLANNER_REASONING_EFFORT`. `DEEPSEEK_CHAT_MODEL` remains the
  backward-compatible fallback.
- Live runtime can enable the provider with `AI_PROVIDER=deepseek`; missing or
  failing provider calls still fall back deterministically.
- Material extraction uses a bounded Pro -> Flash -> deterministic path, so a
  slow or unavailable planning model does not block the upload flow forever.
- The DeepSeek SDK's hidden retry loop is disabled in favor of the app-level
  timeout/retry/fallback policy, keeping Telegram interactions predictable.
