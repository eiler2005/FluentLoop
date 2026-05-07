# ADR-0006 — Public Git Secret Hygiene

**Status:** Accepted
**Date:** 2026-05-07
**Deciders:** Denis Ermilov

## Context

FluentLoop is moving toward a public git repository. The code is safe to share,
but runtime values are not: Telegram tokens, Telegram numeric user/chat ids,
OpenAI/Anthropic keys, VPS coordinates, SQLite learning data, bot session files,
and user lesson text all identify or control the live personal bot.

`router_configuration` uses a repo-specific scanner and a strict
secrets-outside-git policy. FluentLoop should follow the same pattern with
checks tailored to Telegram and AI-provider risks.

## Decision

Tracked files contain implementation logic and placeholders only.

Real values stay in gitignored runtime locations:

- `.env` and `.env.*`
- `secrets/`
- `data/`, including SQLite DBs, sessions, backups, generated Telegram assets,
  usage logs, answers, and lesson text
- `reports/`, `state/`, and `feedback_disputes/`

The repository includes a local pre-commit hook and CI step that run
`scripts/secret_scan.py`. The scanner checks tracked and untracked non-ignored
text files for Telegram bot tokens, AI API keys, private key markers, public
VPS IP literals, real-looking secret env assignments, known sensitive literals,
and email addresses.

## Consequences

- Public GitHub history should contain placeholders such as `<vps-host>`,
  `<your-telegram-user-id>`, and `example.invalid`, not production values.
- Deploy and smoke scripts must get live coordinates from environment or
  gitignored `.env`/`secrets/` files.
- Before publishing or pushing, run `python3 scripts/secret_scan.py` plus the
  normal ruff/test gate.
- Existing private local history may still contain old operational literals.
  Publish either a sanitized fresh snapshot or a rewritten history only after
  an explicit owner decision.
- The scanner is a guardrail, not a substitute for judgment when adding docs,
  screenshots, reports, or operational handoff notes.
