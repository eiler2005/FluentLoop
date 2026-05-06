# ADR-0002 — Telegram library choice

**Status:** Proposed (stub — to be filled in before EPIC-01 starts)
**Date:** TBD
**Deciders:** TBD

## Context

FluentLoop is a single-user Telegram bot. The user talks to the bot via the
Telegram **Bot API**, not as a personal account. That rules out Telethon
(which targets the user-account API and is the wrong tool for bot
applications, even though it appears in the reference repo
`openclaw_firststeps`).

The realistic candidates are:

- **`aiogram`** (v3.x) — modern async, FSM built in, popular in the Russian
  Python community, opinionated about dispatcher/router structure.
- **`python-telegram-bot`** (v21.x) — older, larger ecosystem, also async,
  more conservative API.

Both are mature and well-maintained.

## Decision

TBD.

## Alternatives considered

- **`aiogram`** — pro: clean async, FSM (useful for multi-step flows like
  upload → extract → approve), terse handler syntax, active community.
  Con: steeper learning curve if unfamiliar with its router/dispatcher
  model.
- **`python-telegram-bot`** — pro: longer track record, larger Stack
  Overflow surface, more conservative API changes. Con: less idiomatic
  async in places, FSM via third-party `telegram.ext.ConversationHandler`.
- **Telethon** — rejected. Targets user-account API. Bot mode exists but
  is a poor fit for a public-facing bot and forces an awkward auth flow.

## Consequences

TBD.

## References

- PRD §21 (commands), §22 (user scenarios)
- [`../architecture.md`](../architecture.md)
- `docs/features/EPIC-01-bot-foundation.md`
