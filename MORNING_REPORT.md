# MORNING_REPORT — overnight Codex session

## Time

- Started: `2026-05-06 19:45 UTC` (`22:45 Moscow`)
- Last updated: `2026-05-06 22:08 UTC` (`01:08 Moscow`)
- Total wall time so far: `02h 23m`

## Epics done

| # | Epic | Commit | Tests | Deployed? | Notes |
|---|---|---|---|---|---|
| 01 | EPIC-01-bot-foundation | this commit | ✅ | ✅ 20:28 UTC | Docker/VPS health + gate audit |
| 02 | EPIC-02-user-profile-settings | this commit | ✅ | skipped | all settings + updated_at audit |
| 03 | EPIC-03-material-upload | this commit | ✅ | skipped | upload service + safe free-text fallback |
| 04 | EPIC-04-ai-extraction-and-approval | this commit | ✅ | skipped | approve-all + one-by-one candidate review |
| 05 | EPIC-05-learning-items | this commit | ✅ | ✅ 21:06 UTC | CRUD + duplicate/status command audit |
| 06 | EPIC-06-spaced-repetition | this commit | ✅ | skipped | 7-day Good interval audit |
| 07 | EPIC-07-automatic-practice-generation | this commit | ✅ | skipped | no repeats + high-confidence mistakes |
| 08 | EPIC-08-daily-practice-telegram | this commit | ✅ | ✅ 20:28 UTC | Start button + completion audit |
| 09 | EPIC-09-exercise-types | this commit | ✅ | skipped | 6-type registry |
| 10 | EPIC-10-answer-checking-feedback | this commit | ✅ | ✅ 22:04 UTC | attempt feedback + dispute command |
| 11 | EPIC-11-mistake-events-and-patterns | this commit | ✅ | skipped | auto ingestion + archive audit |
| 12 | EPIC-12-grammar-rules-graph | this commit | ✅ | skipped | unlink + parent refresher audit |
| 13 | EPIC-13-stats-and-weekly-summary | this commit | ✅ | skipped | weekly job + split audit |
| 14 | EPIC-14-favorites | this commit | ✅ | skipped | 20-item cap + preserve flag |

## Epics stuck

| # | Epic | Question | Reverted? |
|---|---|---|---|
| — | Channel discovery | [Q1](NIGHT_QUESTIONS.md#1-channel-discovery-did-not-expose-fluentloop-english) | no |

## Epics not attempted

- EPIC-15 — Deferred per ADR.

## OpenAI spend

- Total: `$0.00`
- Per epic:
  - EPIC-04: `$0.00` (stub calls only)
  - EPIC-07: `$0.00` (deterministic/stub generation)
  - EPIC-10: `$0.00` (stub calls only)
- Cap status: under `$5`; no real OpenAI calls were made.

## Deploys

| Time (UTC) | Commit | Smoke test | Notes |
|---|---|---|---|
| 20:28 | `this commit` | ✅ Bot API outbound smoke message delivered | deployed to `/opt/fluentloop-bot` |
| 21:02 | `5fa79b5` | ✅ Bot API outbound smoke message delivered | redeployed healthy container after deploy keepalive hardening |

## Surprises / anomalies

- Local system Python is 3.7 and has SSL certificate issues; verification used
  `uv --python 3.11`, which created `.venv/` and passed lint/tests.
- Local Docker daemon was unavailable, but VPS Docker build succeeded and the
  container reached healthy status.
- Bot-mode Telethon handshake passed for the configured bot; Bot API and
  Telethon could not discover the private channel id from available updates.
- `/opt/fluentloop-bot` initially required root-owned directory setup; deploy
  script now uses sudo only to create/chown that service directory.
- Telegram command coverage was widened after the first deploy: `/add`,
  `/upload`, `/approve`, `/favorites`, and `/settings set ...` now have
  practical text-command paths.
- APScheduler jobs were wired into the running bot for daily reminders,
  overnight pre-generation, and SQLite backups.
- Practice answer handling was tightened: `/today` starts/resumes a session,
  while unrelated free text gets a "send /today" prompt instead of creating a
  hidden session.
- Invalid `/add` payloads and oversized uploads now return friendly errors
  instead of crashing handler execution.
- `/mistakes` now shows pattern ids and supports `/mistakes focus <id>` /
  `/mistakes ignore <id>` for promotion/archive.
- `/favorite <item_id>` now toggles favorites from Telegram; add/list output
  includes item ids.
- `/items [active|archived|suspended]` lists learning items, and `/item
  archive|suspend|restore <item_id>` manages lifecycle from Telegram.
- Current green gate: `ruff check src tests scripts` and `pytest -q`
  (`32 passed`).
- EPIC-07/08 audit fix: practice sessions now fill sparse item libraries with
  seed business/IT prompts instead of repeating the same approved item, and
  completion messages include persisted attempt counts.
- Added an idempotent demo-data seeding script for audit/smoke coverage:
  learning items, lesson material, extracted candidates, high-confidence
  mistake pattern, cached session, and completed session.
- EPIC-01-05 strict-audit fixes added coverage for container/gate invariants,
  setting timestamps, one-by-one candidate actions, malformed extraction
  fallback, duplicate `/add` UX, and free-text upload guidance.
- EPIC-06-10 strict-audit fixes added Start-button reminders, 7-answer
  completion coverage, high-confidence mistake refreshers, richer feedback
  messages, and `/dispute <attempt_id> <reason>` with JSONL logging and
  mistake-event removal.
- EPIC-11-14 strict-audit fixes added automatic mistake-pattern ingestion,
  archived-pattern no-recreate coverage, grammar unlink/rule counts, weekly
  summary scheduling/splitting, and `/favorites` 20-item cap coverage.

## Recommended morning order of business

1. Add `TELEGRAM_CHANNEL_ID` to `.env` or create a fresh channel event visible
   to the bot, then rerun `python scripts/discover_channel.py`.
2. Send `/start` manually to the bot in Telegram and check the live UX.
3. Continue hardening inline callback flows for `/settings`, `/add`, approval,
   favorites, and disputes.
