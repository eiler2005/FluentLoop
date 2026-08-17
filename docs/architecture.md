# Architecture

> **Status:** v0.2 — MVP foundation (EPIC-01..14), learning-engine roadmap
> (EPIC-16..21), and EPIC-22/23 extensions are shipped. ADRs 0002-0008 are
> Accepted. Schema specifics
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
              │ Telegram (forum + DM, admitted users)               │
              │   /today  /upload  /library  /lessons  /skip  ...    │
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
- Four Telethon handlers: `NewMessage(pattern="^/")` for commands,
  `CallbackQuery` for inline buttons, `NewMessage` for free text, and
  `Raw(UpdateMessagePollVote)` for native quiz-poll answers (EPIC-25).
- **Telethon owns the update stream.** The Bot API path below can send but
  never receive, so anything needing a reply — quiz polls in particular — must
  go through MTProto. See [ADR-0011](adr/0011-native-telegram-quiz-polls.md).
- **Answer where you were asked.** `_here_or_workspace(event, settings, topic)`
  routes a reply to a forum topic only when the request arrived from the
  workspace; otherwise it answers in the originating chat. Broadcasts (the
  pinned help hub, the `/start` channel hubs) still address the workspace
  directly. See the 2026-08-17 amendment to
  [ADR-0005](adr/0005-forum-workspace-routing.md).
- **A persistent reply keyboard** (Cards / Review / Lesson / My words / Add
  words / Quiz / Stop) is installed by `/start`. Taps arrive as plain text, so
  `handlers.quick_action_for` must run before every free-text capture path.
- **A quiz is a sequence of deliveries**, one `vocab_deliveries` row per
  question, with the `seq=0` claim as the idempotency lock for the set. Rows
  stay `claimed` until answered, which is what makes `/quiz` resumable. See
  the 2026-08-17 amendment to
  [ADR-0011](adr/0011-native-telegram-quiz-polls.md).
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
- Concurrency: one bot process writes to SQLite. Per-user rows are isolated in
  the schema, and `journal_mode = WAL` lets the backup job read while the bot
  writes.

## 3. AI provider — OpenAI two-tier plus an OpenAI-compatible gateway

**Decision:** [ADR-0003](adr/0003-ai-model-tiering-and-cost.md).
**Roadmap update:** [ADR-0007](adr/0007-deepseek-llm-gateway.md).
**Multi-provider:** [ADR-0010](adr/0010-multi-provider-llm-gateway.md).

`AI_PROVIDER` selects one of:

| Value | Provider | Env prefix | Notes |
|---|---|---|---|
| `stub` | none | — | Deterministic. Test and offline default. |
| `openai` | OpenAI | `OPENAI_` | Original MVP path, two-tier (below). |
| `deepseek` | DeepSeek | `DEEPSEEK_` | Learning-engine default since EPIC-18. |
| `qwen` | Qwen (DashScope) | `QWEN_` | Added in EPIC-25. Ignores `reasoning_effort`. |

`deepseek` and `qwen` share one gateway: it speaks the OpenAI-compatible chat
protocol against a configurable `base_url`, and `llm/router.provider_config`
picks the endpoint, models, and usage-log attribution.

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
- Five jobs:
  1. **Daily reminder** — sends the "ready for today's English?" message.
  2. **Overnight pre-gen** — see §4.
  3. **Daily SQLite backup** — snapshot
     `data/fluentloop.sqlite` to `data/backups/db-YYYY-MM-DD.sqlite`,
     keep 14 days.
  4. **Weekly summary** — Sunday digest (EPIC-13).
  5. **`vocab_loop_tick`** — fires every minute and delivers any daily-loop
     slot that is due in the learner's own timezone (EPIC-25).
- Jobs are registered as coroutine functions with `args=[...]`. They must never
  be wrapped in `lambda: asyncio.create_task(...)`: that drops the task
  reference, swallows exceptions, and makes `misfire_grace_time` and
  `max_instances` measure the wrapper rather than the work.
- **Per-user timing** ([ADR-0012](adr/0012-per-user-slot-dispatcher.md)): the
  minute tick resolves each learner's local time from `User.timezone`. A slot
  stays deliverable for 90 minutes, and a `vocab_deliveries` row is claimed
  before sending — its unique constraint on
  `(user_id, local_date, slot, seq)` is what makes the tick idempotent across
  restarts, overlapping ticks, and the repeated hour at the end of DST.
- Date arithmetic for a user is always local, never UTC, so it agrees with
  `PracticeSession.target_date_local`.
- Misfire grace handles container restarts.
- All five run in the same process as the bot (one container).

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
- Deploy via `scripts/deploy.sh`: rsync code and `.env`, build the Docker image,
  run `alembic upgrade head`, start the container, and tail logs. Future Ansible
  playbooks may replace this, but they are not the active deploy path.
- `scripts/smoke_telegram.py` confirms the bot token is reachable and sends a
  Telegram smoke message after deploy.
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

PRD §24 is the product-level source of truth. Key runtime entities:

- `User` — one row per admitted Telegram user/profile. `preferences_json`
  carries the EPIC-25 daily-loop settings (slot times, pause flag, words per
  day, chosen topics/kinds/fun sets, starter size, onboarding stamp) as one
  JSON blob rather than eight columns.
- `SourceMaterial` + `ExtractedCandidate` — upload-and-approve pipeline.
- `MaterialChunk` — bounded local chunks for keyword context search over
  uploaded materials.
- `LearningItem` — words, expressions, grammar rules, mistake patterns.
  EPIC-25 adds `priority` (10 for words the learner typed in themselves, 0 for
  seeded content) and a fourth `status` value, `graduated`, for items that have
  been mastered. Every existing query already filters on `status == "active"`,
  so graduated items leave the rotation without any query change.
- `vocab_deliveries` — one row per delivered daily-loop unit (EPIC-25). Serves
  both slot idempotency and the `poll_id → item` lookup for quiz votes.
- `GrammarConcept` — graph (parent/child) for grammar topics.
- `MistakeEvent` + `MistakePattern` — mistake-as-training loop.
- `ReviewState` — spaced-repetition bookkeeping per learning item.
- `PracticeSession` + `PracticeAttempt` — what happened during practice.
  Practice sessions use `target_date_local` and may be `superseded` when a
  newer active lesson plan replaces an older in-progress daily session.
- `practice_session_cached` — overnight pre-gen output (ADR-0004).
- `LessonPlan` + `LessonStep` + `LessonPlanItem` — reusable staged lesson
  plans linked to source materials and existing learning items. EPIC-23 adds
  `is_template` / `template_of` on lesson plans, source materials, and learning
  items so shared seed lessons can be cloned into per-user progress.
- `EvaluationRun` + `LearningMetricSnapshot` — EPIC-24 learning-outcome data:
  monthly baselines, held-out item sets, Article Lab probes, and 30-day metric
  snapshots for `/outcomes` and Coach Journal context.
- `usage_log` — per-AI-call token counts (cost telemetry).

## TODOs

- [ ] Add a redact-list mechanism for sending lesson notes to the configured
      AI provider (P1 — see [`../SECURITY.md`](../SECURITY.md)).
- [ ] Off-VPS backup strategy (P1).
- [ ] Write a dedicated ADR if/when we add a redact-list mechanism; privacy
      policy and provider behavior make this architectural, not just prompt
      tuning.
