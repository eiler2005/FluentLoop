# Architecture

> **Status:** v0.2 — MVP foundation (EPIC-01..14) and learning-engine roadmap
> (EPIC-16..21) are shipped. ADRs 0002–0007 are Accepted. Schema specifics
> for individual epics live in those epic files.

The PRD deliberately keeps tech choices out of itself. This document is the
single place where those choices are recorded, with the underlying
decisions as ADRs in [`adr/`](adr/).

## TL;DR

- **One Docker container** on a personal VPS, running Python 3.11.
- **Telethon 1.36+ in bot mode** as the Telegram client (ADR-0002).
- **AI provider:** OpenAI two-tier for the original MVP (ADR-0003); DeepSeek
  gateway for the learning-engine roadmap (ADR-0007). Provider abstraction
  picks one based on `AI_PROVIDER`; deterministic fallback exists for offline
  dev and degraded-AI failure modes.
- **SQLite** via SQLAlchemy 2.x, single-file DB, mounted from host.
- **APScheduler** in-process for daily reminders, overnight pre-gen
  (ADR-0004), and daily SQLite backups.
- **Long polling** against Telegram (no webhook, no public ports).
- **Telegram workspace maintenance** syncs Bot API commands, refreshes the
  pinned Help topic, and safely removes only identifiable bot-authored stale
  help/smoke messages.

## At a glance

Component view — every box is one Python module set inside a single Docker
container:

```
              ┌─────────────────────────────────────────────────────┐
              │ Telegram (forum + DM, single allowed user)          │
              │   /today  /upload  /lessons  /skip  ...             │
              └─────────────────────────┬───────────────────────────┘
                                        │ MTProto long-poll + Bot API
                                        ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ src/fluentloop/                                                        │
   │                                                                        │
   │  bot/             ┌─── learning_engine ─── lesson_plans ─── practice ──┤
   │   ├ app.py        │           │                  │              │      │
   │   ├ handlers/  ───┤           ▼                  ▼              ▼      │
   │   ├ state.py      │       materials ─────── exercises ─── mistakes     │
   │   └ workspace/    │           │                  │              │      │
   │                   │           └──────────┬───────┴──────────────┘      │
   │                   │                      ▼                             │
   │                   │       db/  (SQLAlchemy 2.x, Alembic, SQLite)       │
   │                   │                      │                             │
   │                   ▼                      ▼                             │
   │              ai/ provider     llm/ DeepSeek gateway                    │
   │              (OpenAI tiered)  (task-aware, JSON, fallback)             │
   └────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                   APScheduler (in-process, three jobs)
                   ├─ Daily reminder (User.reminder_time)
                   ├─ Overnight pre-gen (PRE_GEN_HOUR=3)
                   └─ Daily SQLite backup (BACKUP_HOUR=4, 14d retention)
```

Daily-loop data flow — what happens between bedtime and the morning's
`/today`:

```
   night                                              morning
  ──────────────────────────────────────────────────────────────
  03:00 user-TZ                                       ~09:00 (or whenever
  APScheduler                                         the reminder fires)
   │                                                          │
   ▼                                                          ▼
  compose_tomorrow_session(user)              /today handler
   │                                                  │
   │  pulls due items + weak items + mistake          │  reads from
   │  patterns + recent material chunks +             │  practice_session_cached
   │  active LessonPlans                              │  (instant start)
   │                                                  │
   ▼                                                  ▼
  practice_session_cached                     learner answers ─┐
  (target_date_local, user_id)                                 │
                                                       answer-check  ──► AI
                                                       (DeepSeek Flash)   gateway
                                                              │
                                                              ▼
                                                       feedback + SRS update
                                                       + mistake event log
                                                       + stats / favorites
```

## Runtime topology

One Docker container (`python:3.11-slim`) running:

- the Telethon long-poll loop,
- APScheduler with three cron-style jobs,
- the SQLite database on `/app/data` (host-mounted),
- session files on `/app/data/sessions/`,
- daily backups on `/app/data/backups/` (14-day rotation),
- the dispute log on `/app/data/feedback_disputes/`.

No public ports. No webhook. No external orchestrator. Restarts are safe
(state lives in SQLite + the persisted Telethon session).

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
- Bot API is used for forum-topic sends, pins, command-menu sync, and Help-topic
  maintenance where MTProto topic ergonomics are weaker.
- `/help` and `/howto` render the same learner guide. `/start` and `/help`
  refresh the forum Help topic when workspace routing is configured; operators
  can also run `scripts/telegram_workspace_maintenance.py`.
- Rate limiting: Telethon handles `FloodWait` automatically.

## 2. Database — SQLite

- Engine: SQLite via SQLAlchemy 2.x.
- File: `data/fluentloop.sqlite`, mounted from host into the container
  at `/app/data/fluentloop.sqlite`.
- Migrations: Alembic from day 1.
- Concurrency: single user, single writer, no contention. `journal_mode
  = WAL` to allow the backup job to read while the bot writes.

## 3. AI provider — OpenAI two-tier plus DeepSeek gateway

**Decision:** [ADR-0003](adr/0003-ai-model-tiering-and-cost.md).
**Roadmap update:** [ADR-0007](adr/0007-deepseek-llm-gateway.md).

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
- Privacy: lesson notes, mistakes, and answers go to the configured AI
  provider. See
  [`../SECURITY.md`](../SECURITY.md) for the disclosure and the
  P1-tracked optional redaction list.

For EPIC-18 onward, DeepSeek is available through `src/fluentloop/llm/` using
the OpenAI-compatible API. Runtime can select it with `AI_PROVIDER=deepseek`
and the `DEEPSEEK_*` env variables. Business modules must call the gateway or
`AIProvider` abstraction rather than constructing provider clients directly.
The router uses task-aware profiles: Pro for teacher planning and substantial
lesson extraction, Flash for high-frequency answer checks and concise exercise
generation.

Current learning-engine runtime behavior:

- Material extraction and lesson planning try the planner/extractor profile
  first, then the fast profile, then deterministic fallback.
- Answer checking defaults to the fast profile and stores layered teacher
  feedback for compact and detailed rendering.
- The DeepSeek client's hidden SDK retries are disabled; FluentLoop owns the
  bounded timeout/retry/fallback policy so Telegram flows do not hang.
- The upload prompt is compact and requests a lesson overview, knowledge areas,
  and a 20-30 item candidate pool for substantial lesson notes.

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
- Current Learning Engine sessions are keyed by the user's local date
  (`User.timezone`). If an in-progress legacy/stale session conflicts with a
  newly approved active LessonPlan, the stale session is marked `superseded`
  and `/today` starts the current lesson-plan session.

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

- Legacy AI prompts live as constants in `src/fluentloop/prompts/*.py`; the
  learning-engine gateway prompts live in `src/fluentloop/llm/prompts.py`.
  Both styles should keep explicit input/output schema references.
- Output schemas live in `src/fluentloop/ai/schemas.py` and
  `src/fluentloop/llm/schemas.py` (Pydantic). Mismatched output goes through
  bounded retry/fallback rather than crashing the Telegram flow.
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
- Telegram callback acknowledgements can expire during slower live operations
  such as approving a large candidate pool. Callback-answer failures should be
  logged and ignored after the DB work has succeeded; they must not roll back
  extraction approval or practice progress.

## 10. Deployment

- Single Docker container on a VPS, image built from a small
  `python:3.11-slim` base.
- `docker-compose.yml` mounts `./data:/app/data` (DB, sessions,
  backups, dispute logs).
- Deploy via SSH + ansible — pattern lifted from
  `aiprojects/vps_management`. Playbooks land in a future epic.
- `verify.sh` confirms the container is up and the bot answers
  `/start`.
- `scripts/telegram_workspace_maintenance.py` is the post-deploy workspace
  refresh path: it calls Bot API `setMyCommands`, clears Help-topic pins,
  optionally deletes only bot-authored stale help/smoke messages, and pins the
  current guide.

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
- `MaterialChunk` — bounded local chunks for keyword context search over
  uploaded materials.
- `LearningItem` — words, expressions, grammar rules, mistake patterns.
- `GrammarConcept` — graph (parent/child) for grammar topics.
- `MistakeEvent` + `MistakePattern` — mistake-as-training loop.
- `ReviewState` — spaced-repetition bookkeeping per learning item.
- `PracticeSession` + `PracticeAttempt` — what happened during practice.
  Practice sessions use `target_date_local` and may be `superseded` when a
  newer active lesson plan replaces an older in-progress daily session.
- `practice_session_cached` — overnight pre-gen output (ADR-0004).
- `LessonPlan` + `LessonStep` + `LessonPlanItem` — reusable staged lesson
  plans linked to source materials and existing learning items.
- `usage_log` — per-AI-call token counts (cost telemetry).

## TODOs

- [ ] Add a redact-list mechanism for sending lesson notes to the configured
      AI provider (P1 — see [`../SECURITY.md`](../SECURITY.md)).
- [ ] Wire up `verify.sh` once the container exists (EPIC-01 deliverable).
- [ ] Off-VPS backup strategy (P1).
- [ ] Decide ADR-0005 if/when we add a redact list (worth its own ADR
      because of the privacy-policy implications).
