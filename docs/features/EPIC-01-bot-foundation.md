# EPIC-01 — Bot foundation

**Status:** Planned
**PRD references:** §21 (commands), §22 (user scenarios — base layer)
**Depends on:** ADR-0002 (Telegram library choice)
**Blocks:** every other epic

## Goal

A running Telegram bot that the user can talk to, with the project skeleton
(Python package, Dockerfile, `docker-compose.yml`, requirements / pyproject,
basic logging) in place. The bot does almost nothing yet — but `/start` and
`/help` work, the container builds and runs, and there is a place to plug in
the next epics without restructuring.

## In scope

- Choose Telegram library per ADR-0002, add to dependencies.
- Project skeleton: `src/fluentloop/`, `tests/`, `Dockerfile`,
  `docker-compose.yml`, `pyproject.toml` or `requirements.txt`.
- Logging configured from `LOG_LEVEL` env var, JSON-friendly format.
- `/start` — greeting message, mention next steps.
- `/help` — list of commands (initially just `/start` and `/help`).
- Long-polling against Telegram Bot API (no webhook).
- Single-user gate: if `TELEGRAM_ALLOWED_USER_ID` is set and the message
  comes from a different user, reply with a polite "this is a personal bot"
  and ignore.
- Basic CI-able commands: `ruff check`, `pytest -q` (even with one trivial
  test), `python -m fluentloop --help`.

## Out of scope

- Profile / settings UI → EPIC-02.
- Persistence → EPIC-05.
- Any business logic → EPIC-03 onward.
- Deployment automation (ansible) → later epic.

## Acceptance criteria

- `docker compose up --build` brings the bot up; logs show "polling started".
- Sending `/start` to the bot from the allowed Telegram account returns the
  greeting.
- Sending `/start` from a non-allowed account returns the personal-bot
  message (when `TELEGRAM_ALLOWED_USER_ID` is set).
- `/help` lists `/start` and `/help`.
- `ruff check src tests` passes.
- `pytest -q` passes (one smoke test asserting the app constructs).

## Open questions

- ADR-0002 not yet decided (`aiogram` vs `python-telegram-bot`).
- Container image: `python:3.11-slim` (matches `openclaw_firststeps`) vs
  `python:3.12-slim`. Default to 3.11 unless a dependency requires newer.
- Project layout: src-layout (`src/fluentloop/__init__.py`) vs flat. Default
  src-layout.

## Verification plan

1. `docker compose build` succeeds.
2. `docker compose up` produces "polling started" within ~3 seconds.
3. Manually `/start` and `/help` from your Telegram account.
4. With `TELEGRAM_ALLOWED_USER_ID` set, ask a friend to message the bot —
   confirm they get the personal-bot reply.
5. `docker compose down` cleanly stops the container.
