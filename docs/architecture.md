# Architecture

> **Status:** v0.1 — decisions for EPIC-01 are locked. ADRs 0002–0004 are
> Accepted. Schema specifics for individual epics live in those epic files.

The PRD deliberately keeps tech choices out of itself. This document is the
single place where those choices are recorded, with the underlying
decisions as ADRs in [`adr/`](adr/).

## TL;DR

- **One Docker container** on a personal VPS, running Python 3.11.
- **Telethon 1.36+ in bot mode** as the Telegram client (ADR-0002).
- **OpenAI two-tier:** `gpt-4o-mini` (light) + `gpt-4o` (heavy) (ADR-0003).
- **SQLite** via SQLAlchemy 2.x, single-file DB, mounted from host.
- **APScheduler** in-process for daily reminders, overnight pre-gen
  (ADR-0004), and daily SQLite backups.
- **Long polling** against Telegram (no webhook, no public ports).

## 1. Telegram client — Telethon (bot mode)

**Decision:** [ADR-0002](adr/0002-telegram-library-choice.md).

- Library: `telethon==1.36.0` (matches `aiprojects/openclaw_firststeps`
  for operational continuity).
- Mode: `TelegramClient.start(bot_token=…)`. No phone, no 2FA.
- Required env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`,
  `TELEGRAM_API_HASH` (the latter two are needed even in bot mode
  because Telethon speaks MTProto).
- Session file: `data/sessions/fluentloop-bot.session`. Mount the
  `data/` dir into the container so the session persists across
  restarts.
- FSM: not built in. Implement a small per-`(chat_id, user_id)` state
  helper in `src/fluentloop/bot/state.py` (~50–100 LoC, persisted in
  SQLite so restarts don't lose mid-flow state).
- Inline keyboards: `telethon.tl.custom.Button.inline(...)`.
- Rate limiting: Telethon handles `FloodWait` automatically.

## 2. Database — SQLite

- Engine: SQLite via SQLAlchemy 2.x.
- File: `data/fluentloop.sqlite`, mounted from host into the container
  at `/app/data/fluentloop.sqlite`.
- Migrations: Alembic from day 1.
- Concurrency: single user, single writer, no contention. `journal_mode
  = WAL` to allow the backup job to read while the bot writes.

## 3. AI provider — OpenAI two-tier

**Decision:** [ADR-0003](adr/0003-ai-model-tiering-and-cost.md).

| Tier | Model | Tasks |
|---|---|---|
| Light | `gpt-4o-mini` | Cloze checking, exact-match translation, mistake-type classification. |
| Heavy | `gpt-4o` | Material extraction, grammar feedback, "more natural" rewrites, weekly report, mistake-pattern detection. |

- SDK: `openai>=1.40.0`.
- Structured outputs: `response_format=json_schema` with Pydantic
  models — see `src/fluentloop/ai/schemas.py`.
- Abstraction: `src/fluentloop/ai/provider.py` exposes `light_call()`
  and `heavy_call()`, both returning Pydantic-validated results. Tier
  choice is per *task type*, not per call site.
- Cost telemetry: `usage_log` table (or JSONL) with token counts per
  call, summed weekly.
- Privacy: lesson notes, mistakes, and answers go to OpenAI. See
  [`../SECURITY.md`](../SECURITY.md) for the disclosure and the
  P1-tracked optional redaction list.

## 4. Pre-generation pipeline

**Decision:** [ADR-0004](adr/0004-exercise-pre-generation-strategy.md).

- APScheduler `cron` trigger fires `compose_tomorrow_session` at 03:00
  local user TZ.
- Output cached in `practice_session_cached` keyed by
  `(user_id, target_date_local)`.
- `/today` and the daily reminder serve from cache → instant start.
- Answer checking is real-time (not cacheable).
- On-demand fallback if the cache is missing or stale; user sees
  "preparing exercises…".
- Tunable via env: `PRE_GEN_HOUR=3`, `PRE_GEN_MINUTE=0`.

## 5. Scheduler — APScheduler in-process

- `apscheduler==3.10.4` (matches `openclaw_firststeps`).
- Three jobs:
  1. **Daily reminder** — fires at `User.reminder_time` in
     `User.timezone`, sends the "ready for today's English?" message.
  2. **Overnight pre-gen** — see §4.
  3. **Daily SQLite backup** — snapshot
     `data/fluentloop.sqlite` to `data/backups/db-YYYY-MM-DD.sqlite`,
     keep 14 days.
- Misfire grace handles container restarts.
- All three run in the same process as the bot (one container).

## 6. Prompt structure

- Prompts live as constants in `src/fluentloop/prompts/*.py` —
  per-task module, f-string templates with explicit input/output schema
  references.
- Output schemas live in `src/fluentloop/ai/schemas.py` (Pydantic).
  Mismatched output → one retry on heavy tier → user-friendly fallback.
- Prompt versions are tagged in code (`EXTRACT_PROMPT_VERSION = "v1"`)
  and logged with each call so model upgrades or prompt tweaks are
  traceable in the cost log.

## 7. Secrets management

- Plain `.env` file on the VPS, mounted into the container via
  `env_file: .env` in `docker-compose.yml`. No vault for MVP.
- Pre-commit: scan staged diff for token-shaped strings. See
  [`../SECURITY.md`](../SECURITY.md).
- Real values never appear in logs (mask token-shaped strings in the
  formatter).

## 8. Backups

- APScheduler runs a daily SQLite snapshot to
  `data/backups/db-YYYY-MM-DD.sqlite`.
- 14-day rotation; older files deleted by the same job.
- Off-VPS backup (B2 / restic / rsync to a second host) is a P1
  enhancement, not MVP. Captured in `docs/runbooks/backup-offsite.md`
  when that runbook is written.

## 9. Logging & observability

- `LOG_LEVEL=INFO` to stdout; Docker's json-file driver captures.
- Mask any string matching the bot-token / OpenAI-key shape.
- Optional `/health` HTTP endpoint inside the container (not exposed
  publicly) for VPS-side monitoring — defer to a deployment epic.
- AI feedback disputes (EPIC-10): user thumbs-down writes to
  `feedback_disputes/YYYY-MM-DD.jsonl` for later audit.

## 10. Deployment

- Single Docker container on a VPS, image built from a small
  `python:3.11-slim` base.
- `docker-compose.yml` mounts `./data:/app/data` (DB, sessions,
  backups, dispute logs).
- Deploy via SSH + ansible — pattern lifted from
  `aiprojects/vps_management`. Playbooks land in a future epic.
- `verify.sh` confirms the container is up and the bot answers
  `/start`.

## 11. Web UI — deferred

EPIC-15 is `Status: Deferred — re-evaluate after 4–6 weeks of real bot
usage`. Adding auth + hosting + framework + CSP early creates a second
project inside the first. In-Telegram editing via inline keyboards
covers ~90% of management needs.

## Container shape (working assumption)

```yaml
# docker-compose.yml — concrete version comes in EPIC-01.
services:
  fluentloop:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data       # SQLite, sessions, backups, dispute logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import os; assert os.path.exists('/app/data/fluentloop.sqlite')"]
      interval: 60s
      timeout: 5s
      retries: 3
```

No public ports — Telethon long-polls the Telegram MTProto layer.

## Data model overview

PRD §24 is the source of truth. Key entities for MVP (EPIC-05 through
EPIC-13):

- `User` — single row.
- `SourceMaterial` + `ExtractedCandidate` — upload-and-approve pipeline.
- `LearningItem` — words, expressions, grammar rules, mistake patterns.
- `GrammarConcept` — graph (parent/child) for grammar topics.
- `MistakeEvent` + `MistakePattern` — mistake-as-training loop.
- `ReviewState` — spaced-repetition bookkeeping per learning item.
- `PracticeSession` + `PracticeAttempt` — what happened during practice.
- `practice_session_cached` — overnight pre-gen output (ADR-0004).
- `usage_log` — per-AI-call token counts (cost telemetry).

## TODOs

- [ ] Add a redact-list mechanism for sending lesson notes to OpenAI
      (P1 — see [`../SECURITY.md`](../SECURITY.md)).
- [ ] Wire up `verify.sh` once the container exists (EPIC-01 deliverable).
- [ ] Off-VPS backup strategy (P1).
- [ ] Decide ADR-0005 if/when we add a redact list (worth its own ADR
      because of the privacy-policy implications).
