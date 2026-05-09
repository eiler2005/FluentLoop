# EPIC-01 — Bot foundation

**Status:** Done (2026-05-06 19:58 UTC)
**PRD references:** §21 (commands), §22 (user scenarios — base layer)
**Depends on:** ADR-0002 (Telegram library choice — **Accepted: Telethon bot mode**)
**Blocks:** every other epic

## Goal

A running Telegram bot that the user can talk to, with the project skeleton
(Python package, Dockerfile, `docker-compose.yml`, requirements / pyproject,
basic logging) in place. The bot does almost nothing yet — but `/start` and
`/help` work, the container builds and runs, and there is a place to plug in
the next epics without restructuring.

## In scope

- Add dependencies per ADR-0002 / ADR-0003 / docs/architecture.md:
  `telethon==1.36.0`, `apscheduler==3.10.4`, `python-dotenv==1.0.1`,
  `pytz==2024.1`, `sqlalchemy>=2.0`, `alembic>=1.13`, `openai>=1.40.0`,
  `pydantic>=2.7`.
- Project skeleton: `src/fluentloop/{__init__.py,__main__.py,bot/,
  ai/,db/,prompts/,seeds/}`, `tests/`, `Dockerfile`, `docker-compose.yml`,
  `pyproject.toml`, Alembic config in `alembic.ini` + `migrations/`.
- Logging configured from `LOG_LEVEL` env var; mask token-shaped strings
  in the formatter.
- Telethon client wired in bot mode: `TelegramClient(SESSION_PATH,
  TELEGRAM_API_ID, TELEGRAM_API_HASH).start(bot_token=TELEGRAM_BOT_TOKEN)`.
  Session file path: `data/sessions/fluentloop-bot.session`.
- `/start` — greeting message, mention next steps.
- `/help` and `/howto` — the learner guide: how to start practice, browse
  lessons, upload material, answer, skip, and inspect feedback.
- Long-polling via Telethon (`client.run_until_disconnected()`).
- Single-user gate: if `TELEGRAM_ALLOWED_USER_ID` is set and the
  message comes from a different user, reply with a polite "this is a
  personal bot" and ignore.
- Tiny FSM helper at `src/fluentloop/bot/state.py` — per
  `(chat_id, user_id)` state dict persisted in SQLite. ~50–100 LoC,
  enough for upload→extract→approve in EPIC-03/04 and `/settings` in
  EPIC-02.
- Basic CI-able commands: `ruff check`, `pytest -q` (with one smoke
  test asserting the app constructs), `python -m fluentloop --help`.

## Out of scope

- Profile / settings UI → EPIC-02.
- Persistence → EPIC-05.
- Any business logic → EPIC-03 onward.
- Deployment automation (ansible) → later epic.

## Acceptance criteria

- `docker compose up --build` brings the bot up; logs show "Telethon
  bot connected as @<bot-username>".
- Sending `/start` to the bot from the allowed Telegram account returns
  the greeting.
- Sending `/start` from a non-allowed account returns the personal-bot
  message (when `TELEGRAM_ALLOWED_USER_ID` is set).
- `/help` and `/howto` show the current learner guide and include the core
  command list.
- The session file persists across container restarts (mounted via
  `./data:/app/data`).
- `ruff check src tests` passes.
- `pytest -q` passes (one smoke test asserting the app constructs and
  the FSM helper round-trips a state dict).

## Open questions

- Container image: `python:3.11-slim` (matches `openclaw_firststeps`) is
  default unless a dependency requires newer.
- Where exactly to put Alembic — top-level `migrations/` (matches most
  tutorials) vs `src/fluentloop/db/migrations/`. Default: top-level for
  Alembic CLI ergonomics.

## Verification plan

1. `docker compose build` succeeds.
2. `docker compose up` produces "polling started" within ~3 seconds.
3. Manually `/start` and `/help` from your Telegram account.
4. With `TELEGRAM_ALLOWED_USER_ID` set, ask a friend to message the bot —
   confirm they get the personal-bot reply.
5. `docker compose down` cleanly stops the container.

## Notes from implementation

- Added Docker/Python 3.11 runtime, package skeleton, Telethon bot mode wiring,
  `/start`, `/help`, single-user gate, logging, SQLite-backed FSM, and tests.
- `/howto` now aliases `/help`; the Telegram command-menu payload is covered by
  tests and synced by the workspace maintenance script.
- Docker daemon was not reachable locally, so the green gate ran through
  `uv --python 3.11`; Docker files are ready for VPS/Docker verification.
- Audit coverage now asserts the single-user gate, Docker data mount, and
  container command; VPS deploy verifies Telethon connection and health.
