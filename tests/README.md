# Tests

Pytest suite for FluentLoop. Twenty-seven test modules organized by epic and by
operational concern. The suite must stay green on every commit; CI enforces it
via `.github/workflows/ci.yml`.

## How to run

```bash
# Full suite (the standard gate)
uv run --extra dev pytest -q

# Verbose, with the actual test names
uv run --extra dev pytest -v

# A single epic group
uv run --extra dev pytest -v -k epic08

# Just the last failing tests
uv run --extra dev pytest --lf

# Without uv (system Python 3.11+ with the project installed)
pytest -q
```

The full standard gate (lint + tests + smoke checks) lives in
[`../docs/testing.md`](../docs/testing.md).

## Coverage map

Tests are organized by epic, with a few cross-cutting modules for tooling.
Every module exercises the real SQLAlchemy schema against an in-memory SQLite
and stubs the Telegram client and AI providers — no real network calls.

| Test module | Covers |
|---|---|
| `test_epic01_foundation.py` | Bot startup, config loader, Telegram allowed-user gate, command catalog, logging masking. |
| `test_epic02_05_users_learning.py` | User profile + settings flow; LearningItem CRUD, status changes, duplicate handling. |
| `test_epic03_04_10_11_ai.py` | Material upload → AI extraction → candidate approval → answer-check feedback → mistake-event ingestion. |
| `test_epic06_09_08_practice.py` | Spaced repetition intervals, exercise-type registry, daily practice session shape. |
| `test_epic07_12_13_14_channel.py` | Practice composition, grammar concept graph, weekly stats, favorites cap, channel send/route helpers. |
| `test_epic08_scheduler.py` | APScheduler wiring: daily reminder, 03:00 pre-gen, 04:00 SQLite backup, retention. |
| `test_epic17_lesson_plans.py` | Reusable LessonPlan persistence, lesson browser commands, B2/B2+ catalog seed. |
| `test_epic18_deepseek_gateway.py` | DeepSeek gateway routing (Pro vs Flash), JSON contract, fallback path on errors and timeouts. |
| `test_epic19_ai_exercise_generator.py` | AI-assisted high-value exercise generation with deterministic guardrails. |
| `test_epic20_grammar_brain.py` | Practical business/IT grammar concepts and refresher selection. |
| `test_epic21_material_context.py` | Material chunking and lightweight keyword retrieval. |
| `test_epic22_breakthrough.py` | Layered feedback, sub-day GIR, L1 traps, reflection, lesson formats, chunk import, and operational drills. |
| `test_epic22_migration.py` | Alembic upgrade/downgrade/upgrade roundtrip for EPIC-22/23 schema additions. |
| `test_epic23_lesson_library.py` | Shared seed library publishing, `/library`, `/subscribe`, duplicate clone reuse, private visibility, and owner-only publish. |
| `test_epic24_outcomes.py` | `/baseline`, `/outcomes`, held-out retention, productive chunks, L1 density, mistake extinction, Article Lab probes, and outcome snapshots. |
| `test_epic25_vocab_model.py` | Daily-loop preferences, JSON round-trip after commit, graduation thresholds, and user-added priority ordering. |
| `test_epic25_migration.py` | Migration `0004_epic25` upgrade/downgrade round-trip and idempotency. |
| `test_epic25_vocab_commands.py` | Slot windows, card rendering, word-list detection, bulk add, and `/words` `/more` `/learned` `/delete` `/pause` `/resume`. |
| `test_epic25_vocab_scheduler.py` | Minute-tick delivery per timezone, restart idempotency, catch-up window, job registration, and the UTC-date regression. |
| `test_epic25_quiz.py` | Distractor selection, quiz assembly, answering, and the midday drill state machine. |
| `test_epic25_quiz_polls.py` | Native poll construction, vote resolution, and the inline-button fallback. |
| `test_epic25_wordbank.py` | Word-bank validation, deterministic starter selection, and idempotent seeding. |
| `test_epic25_onboarding.py` | The `/setup` wizard state machine end to end. |
| `test_epic25_qwen_provider.py` | Provider selection, model routing, gateway attribution, and DeepSeek back-compat. |
| `test_bot_upload_documents.py` | Telegram document-upload handler: text decoding, oversize rejection, friendly errors. |
| `test_seed_demo_data.py` | Idempotency and shape of `scripts/seed_demo_data.py`. |
| `test_smoke_telegram.py` | Smoke message format: build/time/plan-note headers, sanitized payloads. |
| `test_telegram_workspace_maintenance.py` | `setMyCommands` payload, Help-topic refresh, safe deletion of bot-authored stale messages. |
| `test_secret_scan.py` | `scripts/secret_scan.py` matches token/key shapes and exits non-zero only on real-looking values. |

## Patterns

- **Async**: `pytest-asyncio` with `asyncio_mode = "auto"` (see `pyproject.toml`).
  Async tests are plain `async def`, no decorator boilerplate.
- **In-memory SQLite**: every test gets a fresh `sqlite:///:memory:` engine via
  the `settings` fixture in `conftest.py`. No filesystem state leaks between
  tests.
- **Stub AI**: `AI_PROVIDER=stub` is the default in tests; the stub provider
  returns deterministic JSON shaped to match the real schemas. Tests that
  exercise the OpenAI / DeepSeek code paths use small fakes that reject any
  real network call.
- **Telegram mocks**: handlers receive a fake Telethon event with the minimal
  surface needed (chat id, sender id, text/document attribute). Outbound
  messages are captured in a list and asserted on.
- **No real secrets**: `conftest.py` injects sentinel-only values
  (`telegram_bot_token="token"`, `openai_api_key="STUB_OVERNIGHT_BUILD"`).
  CI runs `scripts/secret_scan.py` on every push so accidentally committed
  real values fail the build.

## Adding a test

1. Pick the matching `test_epicNN_*.py` module — or create a new
   `test_epicNN_<area>.py` if the epic doesn't have one yet.
2. Use the existing fixtures in `conftest.py` (`settings`, `session_factory`,
   the in-memory `engine`). Don't roll your own DB.
3. If you need a Telegram interaction, build the smallest possible fake
   event; don't pull in the live Telethon client.
4. If you need an AI response, set `AI_PROVIDER=stub` and assert on the
   structured output, not on prose.
5. Keep tests deterministic. No real time (`freezegun` or fixed
   `datetime.now()` substitutes), no network, no random seeds without an
   explicit seed.

## CI gate

`.github/workflows/ci.yml` runs on every push and PR:

```bash
python scripts/secret_scan.py          # no real-looking tokens in tracked files
ruff check src tests scripts           # style and basic correctness
pytest -q                              # 121+ tests, < 30 seconds locally
```

A red CI is a hard gate — no merges to `main` while the gate is broken.
