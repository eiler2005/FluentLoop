# ADR-0010 — Multi-provider LLM gateway (Qwen alongside DeepSeek)

**Status:** Accepted
**Date:** 2026-08-17
**Deciders:** Denis Ermilov
**Amends:** ADR-0003, ADR-0007

## Context

ADR-0007 introduced `src/fluentloop/llm/` as a "DeepSeek gateway". In practice
the code was never DeepSeek-specific: it talks the OpenAI-compatible chat
protocol through `clients.make_openai_compatible_client`, which already accepts
an arbitrary `base_url`. The vendor name lived only in the class name, the
config field prefixes, and the `provider` string written to the usage log.

Qwen exposes an OpenAI-compatible endpoint through DashScope, supports
`response_format={"type": "json_object"}`, and ignores `reasoning_effort`.
Adding it therefore costs configuration plus a thin selection layer, not a
second gateway.

## Decision

Treat the gateway as protocol-level rather than vendor-level, and select the
provider through the existing `AI_PROVIDER` switch.

- `AI_PROVIDER` accepts `stub`, `openai`, `deepseek`, and now `qwen`.
- New env vars, all optional: `QWEN_API_KEY`, `QWEN_BASE_URL`,
  `QWEN_CHAT_MODEL`, `QWEN_FAST_MODEL`, `QWEN_PLANNER_MODEL`,
  `QWEN_EXTRACTOR_MODEL`, `QWEN_TIMEOUT_SECONDS`, `QWEN_MAX_RETRIES`.
  `DASHSCOPE_API_KEY` is accepted as a fallback name for the key, because that
  is what Alibaba's own SDK uses and what the sibling `reddit-compass` project
  already stores.
- Base URL `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`.

### Model choice and its evidence

Model defaults are taken from operational measurements in the sibling
`reddit-compass` project (`docs/QWEN_ROUTING.md`, prices verified against
Model Studio in August 2026), not from guesswork:

| Model | List price / 1M in-out | Relative input cost |
|---|---|---|
| `qwen3.7-flash` | CNY 0.225 / 0.974 | 1x |
| `qwen3.6-flash` | CNY 1.874 / 11.241 | ~8x |
| `qwen3.8-max` | CNY 14.988 / 44.965 | ~66x |

The newest flash is also the cheapest, so there is no cost argument for an
older flash either.

**Every FluentLoop LLM task is bounded JSON.** All of them — including
`SEED_LESSON_PLAN`, which returns a Pydantic `LessonPlanDraft` — are validated
against a schema rather than being free-form prose. That is precisely the
class `reddit-compass` measured flash as adequate for, having reserved Max for
genuine synthesis over large inputs. FluentLoop has no such task, so **flash is
the default for every tier**, planner included.

`QWEN_PLANNER_MODEL` can be raised to `qwen3.8-max` if lesson-plan quality
measurably degrades, but the burden of proof is on the upgrade: it is a 66x
input-cost step.

**The key must be pay-as-you-go.** A Token Plan key targets
`token-plan…maas.aliyuncs.com` and returns 404 for the flash models, which is
a failure mode that project hit in production.
- `llm/router.py` gains `ProviderConfig` and `provider_config(settings)`. Both
  `task_profile` and the new `llm_gateway(settings)` read from it instead of
  reaching into `cfg.deepseek_*` directly.
- `DeepSeekGateway` gains a `provider_name` constructor argument, used for
  usage-log attribution and error strings. `LLMGateway` is an alias for it.
- `QwenProvider` subclasses `DeepSeekProvider`, supplying Qwen defaults and
  `provider_name="qwen"`. `reasoning_effort` is `None` for Qwen, so
  `SEED_LESSON_PLAN` runs without the thinking flag.
- `deepseek_gateway` remains as a deprecated alias of `llm_gateway`.

## Consequences

**Positive**

- Provider choice is one env var. No call site knows which vendor is active.
- Usage logs attribute cost to the right provider, so `usage_log.jsonl` stays
  meaningful across a switch.
- Every existing `DEEPSEEK_*` variable keeps working unchanged; `AI_PROVIDER`
  values `deepseek`, `openai`, and `stub` behave exactly as before.

**Negative**

- `Settings` now mixes required and defaulted fields. Every field added from
  here on must carry a default and be appended at the end, or existing
  `Settings(...)` construction sites break.
- Qwen and DeepSeek do not produce identical JSON for the same prompt. Prompt
  changes must be sanity-checked against whichever provider is deployed.

**Neutral**

- The class is still named `DeepSeekGateway` internally. Renaming it would
  churn ADR-0007's tests for no functional gain; the `LLMGateway` alias carries
  the intent.

## Alternatives considered

- **A second, parallel Qwen gateway.** Rejected: it would duplicate the
  retry, validation, fallback, and usage-logging policy that ADR-0007
  deliberately centralised.
- **LangChain or LiteLLM for provider abstraction.** Rejected for the same
  reason as ADR-0007: the dependency is far larger than the ~40 lines of
  selection logic it would replace.
