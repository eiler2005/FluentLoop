# MORNING_REPORT — overnight Codex session

## Time

- Started: `2026-05-06 19:45 UTC` (`22:45 Moscow`)
- Last updated: `2026-05-07 05:55 UTC` (`08:55 Moscow`)
- Total wall time so far: `10h 10m`

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
| 08 | EPIC-08-daily-practice-telegram | this commit | ✅ | ✅ 05:26 UTC | channel mode + feedback routing |
| 09 | EPIC-09-exercise-types | this commit | ✅ | skipped | 6-type registry |
| 10 | EPIC-10-answer-checking-feedback | this commit | ✅ | ✅ 22:04 UTC | attempt feedback + dispute command |
| 11 | EPIC-11-mistake-events-and-patterns | this commit | ✅ | ✅ 22:10 UTC | auto ingestion + archive audit |
| 12 | EPIC-12-grammar-rules-graph | this commit | ✅ | ✅ 22:10 UTC | unlink + parent refresher audit |
| 13 | EPIC-13-stats-and-weekly-summary | this commit | ✅ | ✅ 22:10 UTC | weekly job + split audit |
| 14 | EPIC-14-favorites | this commit | ✅ | ✅ 22:10 UTC | 20-item cap + preserve flag |

## Epics stuck

| # | Epic | Question | Reverted? |
|---|---|---|---|
| — | Channel discovery | resolved 2026-05-07 | no |

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
| 21:08 | `5b7254a` | ✅ Bot API outbound smoke message delivered | EPIC-05 item lifecycle commands |
| 21:13 | `fbe0fda` | ✅ Bot API outbound smoke message delivered | EPIC-07/08 practice completion hardening |
| 21:18 | `8691cda` | ✅ Bot API outbound smoke + VPS seed | demo audit seed deployed |
| 21:28 | `e4981c9` | ✅ Bot API outbound smoke + VPS seed | EPIC-01-05 strict audit fixes |
| 22:04 | `4d562fd` | ✅ Bot API outbound smoke + VPS seed | EPIC-06-10 strict audit fixes |
| 22:10 | `113ba96` | ✅ Bot API outbound smoke + VPS seed | EPIC-11-14 strict audit fixes |
| 05:23 | `7cc0cb5` | ✅ private smoke + channel send/delete smoke | channel id discovered and env deployed |
| 05:26 | `a06ae2d` | ✅ private smoke + channel send/delete smoke | practice feedback/next prompts route to channel |
| 05:42 | `3a1c0ae` | ✅ container private smoke + channel send/delete smoke + VPS seed | callback UX + channel logical topic tags |
| 05:48 | `98aefee` | ✅ healthy container + private smoke + channel send/delete smoke + VPS seed | EPIC-04 candidate edit flow |
| 05:54 | `4b5487d` | ✅ healthy container + private smoke + channel send/delete smoke + VPS seed | EPIC-10 Hard override |

## Surprises / anomalies

- Local system Python is 3.7 and has SSL certificate issues; verification used
  `uv --python 3.11`, which created `.venv/` and passed lint/tests.
- Local Docker daemon was unavailable, but VPS Docker build succeeded and the
  container reached healthy status.
- Bot-mode Telethon handshake passed for the configured bot. Channel id
  discovery was later resolved after the bot was added as admin and Bot API
  updates exposed `FluentLoop English`.
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
  (`36 passed`).
- `TELEGRAM_CHANNEL_ID` is now configured in ignored env files and deployed to
  the VPS. Channel send/delete smoke passed; `/today` posts practice to the
  channel, while private answers route feedback/progress/next prompts back to
  the channel.
- Telegram callback UX hardening added inline settings presets, upload
  confirm/cancel, approve all/review/skip all, one-by-one add/skip, favorite
  stars, item lifecycle actions, mistake focus/ignore, and feedback
  acknowledge/dispute buttons. Channel practice posts now carry logical topic
  tags: `#practice_flow`, `#feedback`, `#next_prompt`, `#summary`, and
  `#mistakes`.
- EPIC-04 follow-up hardening added the missing candidate edit flow: inline
  `Edit` → field picker (`Text`, `Meaning`, `Tags`) → private text input →
  edited candidate remains eligible for explicit approval/skip.
- EPIC-10 follow-up hardening added `Hard` override for correct answers; the
  callback converts the existing `Good` SRS result into `Hard` without
  double-counting the review.
- Local Bot API smoke hit a transient SSL EOF on the Mac after this deploy, so
  smoke was rerun inside the VPS Python 3.11 container and passed there.
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

1. Send `/today` manually to the bot in Telegram and check the channel UX.
2. Check callback buttons in Telegram after the latest deploy: `/settings`,
   `/upload`, `/items`, `/favorites`, `/mistakes`, and a short `/today` flow.
