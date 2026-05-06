# ADR-0002 — Telegram library choice

**Status:** Accepted
**Date:** 2026-05-06
**Deciders:** Denis Ermilov

## Context

FluentLoop is a single-user Telegram bot. The user talks to *the bot* via the
Telegram **Bot API** — not as a personal account.

Three options were on the table:

- **`aiogram`** (v3.x) — modern async, FSM built in, idiomatic for Bot API.
- **`python-telegram-bot`** (v21.x) — older, larger ecosystem.
- **`Telethon`** (v1.36+) — primarily a user-account MTProto client, but
  supports a bot mode via `TelegramClient.start(bot_token=...)`.

The reference repo `aiprojects/openclaw_firststeps` already runs Telethon
successfully in production:

- `artifacts/telethon-digest/` — Docker container, `telethon==1.36.0`,
  `apscheduler==3.10.4`, `python-dotenv==1.0.1`.
- Telethon there is used as a **user account** (`TELEGRAM_PHONE`, two-factor
  auth, reading channels the user is subscribed to). The bot token in
  `telethon.env.example` is consumed separately by `poster.py` for posting
  digests via the Bot API.

So the operational pattern (Docker, env layout, APScheduler wiring,
session-file management) is proven; only the *usage mode* differs.

## Decision

Use **Telethon 1.36+ in bot mode** (`TelegramClient.start(bot_token=…)`).

Rationale:

- The user has already deployed and operated Telethon in production. The
  Dockerfile, env layout, session-file conventions, APScheduler integration,
  and runbook patterns transfer directly from `openclaw_firststeps` to
  FluentLoop.
- Telethon supports bot mode natively. It speaks MTProto under the hood, so
  Bot API features available via MTProto (inline keyboards, callback
  queries, message editing, FSM-style flows) are reachable.
- Reduced cognitive load — one Telegram client across the user's projects
  beats two.

## Alternatives considered

- **`aiogram` 3.x** — would be more idiomatic for a Bot API project and ship
  FSM out of the box. Rejected because the user's preference for familiar
  proven patterns outweighs the marginal idiomatic-ness gain. See memory
  `feedback_prefer_familiar_patterns.md`.
- **`python-telegram-bot` 21.x** — also a fine Bot API choice. Same
  rejection reason as aiogram.
- **Telethon as a user account** — explicitly the wrong fit. FluentLoop
  needs a bot (BotFather token, no phone, inline keyboards in chat); a
  user-account approach would require `TELEGRAM_PHONE` + 2FA and lose the
  bot-only UX features.

## Consequences

**Positive:**

- Direct lift of Docker / env / scheduler patterns from `openclaw_firststeps`.
- Single MTProto client across the user's tooling.
- Bot mode in Telethon does not require `TELEGRAM_PHONE`, only a bot token
  (plus `TELEGRAM_API_ID` + `TELEGRAM_API_HASH`, which Telethon needs even
  in bot mode because it speaks MTProto).
- Telethon handles `FloodWait` automatically.

**Negative:**

- Need `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` (from
  https://my.telegram.org → API development tools) in addition to the
  BotFather token. Three secrets instead of one.
- A `.session` file is created and must persist across container restarts
  (mount `./data/sessions/` into the container).
- No built-in FSM — need a small homegrown state machine for multi-step
  flows (upload → extract → approve, settings edit). Plan: a thin
  per-`(chat_id, user_id)` state dict in SQLite, advanced by handler
  functions. ~50–100 LoC.
- Inline-keyboard ergonomics are slightly more verbose than aiogram's
  builders. Acceptable.
- Most Telegram-bot tutorials in the Python ecosystem target aiogram or
  python-telegram-bot — Stack Overflow surface for "Telethon bot mode" is
  smaller. Mitigation: official Telethon docs at
  https://docs.telethon.dev cover bot mode explicitly.

**Follow-ups:**

- Update `.env.example`: add `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
- Update `EPIC-01-bot-foundation.md`: dependency is `telethon==1.36.0`,
  not `aiogram`.
- Update `EPIC-03` and `EPIC-04` notes about FSM — implement a small
  state-machine helper in `src/fluentloop/bot/state.py` rather than
  relying on `aiogram.fsm`.
- Document the session-file persistence requirement in
  `docs/runbooks/restart.md` when that runbook is written.

## References

- PRD §21 (commands), §22 (user scenarios)
- [`../architecture.md`](../architecture.md)
- `docs/features/EPIC-01-bot-foundation.md`
- Reference: `~/aiprojects/openclaw_firststeps/artifacts/telethon-digest/`
- Telethon bot mode: https://docs.telethon.dev/en/stable/concepts/botapi-vs-mtproto.html
