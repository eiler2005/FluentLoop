# Architecture (stub)

> **Status:** Stub. To be filled in once ADRs 0002–0004 are decided.
> Until then, this file is an outline of the questions that the architecture
> needs to answer, lifted from PRD §29.

The PRD deliberately keeps tech choices out of itself. This document is the
single place where those choices are recorded, with the underlying decisions
as ADRs in [`adr/`](adr/).

## Open questions to resolve

Each item below becomes a decision (and likely an ADR) before the relevant
epic starts.

### 1. Bot framework / library

- **Decision needed:** `aiogram` vs `python-telegram-bot` (vs Telethon).
- **ADR:** [`adr/0002-telegram-library-choice.md`](adr/0002-telegram-library-choice.md)
- **Constraint:** This is a Bot API project (the user talks to *the bot*),
  not a user-account project. Telethon — used in `openclaw_firststeps` for
  channel reading — is the wrong tool here.
- **Blocks:** EPIC-01.

### 2. Database

- **Decision needed:** SQLite (single file, simple, fits one container) vs
  Postgres (overkill for one user but more familiar for production code).
- **Default working assumption:** SQLite via SQLAlchemy. Single user, single
  container, no concurrent writers.
- **Blocks:** EPIC-05, EPIC-06.

### 3. AI provider and model tiering

- **Decision needed:** OpenAI vs Anthropic; which model for which task.
- **ADR:** [`adr/0003-ai-model-tiering-and-cost.md`](adr/0003-ai-model-tiering-and-cost.md)
- **Working assumption:** Two-tier strategy.
  - **Light tier** (Haiku 4.5 / GPT-4o-mini class) for routine answer
    checking — fast, cheap, "good enough" for B2+ judgments.
  - **Heavy tier** (Sonnet 4.6 / GPT-4o class) for extraction from raw
    materials, grammar feedback with explanation, and weekly reports.
- **Cost envelope to verify:** roughly 80–100 LLM calls per active week →
  must stay under a budget the user is comfortable with.
- **Blocks:** EPIC-04, EPIC-07, EPIC-10, EPIC-13.

### 4. Pre-generation pipeline

- **Decision needed:** when and how the day's exercises are produced.
- **ADR:** [`adr/0004-exercise-pre-generation-strategy.md`](adr/0004-exercise-pre-generation-strategy.md)
- **Working assumption:** APScheduler fires a "compose tomorrow's session"
  job overnight (e.g. 03:00 local). Generation produces 7+ exercises with
  prompt + expected answer + hint + explanation, cached in the DB. When the
  user `/today`s, the bot serves the cached batch instantly. Answer
  *checking* remains real-time.
- **Blocks:** EPIC-07, EPIC-08.

### 5. Scheduler

- **Decision needed:** APScheduler in-process vs external cron in the host.
- **Default working assumption:** APScheduler inside the bot process. Avoids
  a second container. Misfire grace handles startup race conditions.
- **Blocks:** EPIC-08.

### 6. Prompt structure

- Where prompts live (Python source vs `prompts/*.txt`).
- How they're versioned (so A/B comparing models is sane).
- How extraction / generation / checking output schemas are validated
  (Pydantic models, JSON schema).
- **Blocks:** EPIC-04, EPIC-07, EPIC-10.

### 7. Secrets management

- **Default working assumption:** plain `.env` file on the VPS, mounted into
  the container via `env_file:` in `docker-compose.yml`. No vault for MVP.
- **Pre-commit:** scan staged diff for token-shaped strings. See
  [`../SECURITY.md`](../SECURITY.md).

### 8. Backups

- **Default working assumption:** APScheduler runs a daily SQLite snapshot
  to `data/backups/db-YYYY-MM-DD.sqlite`, keeps the last 14 days, deletes
  older. Off-VPS backup (B2 / restic) is a P1 enhancement, not MVP.
- **Blocks:** EPIC-08.

### 9. Logging & observability

- **Default working assumption:** `LOG_LEVEL=INFO` to stdout, captured by
  Docker's json-file driver. Add a `/health` endpoint for VPS-side monitoring
  later.
- **AI feedback disputes:** when a user thumbs-down an AI verdict, log to
  `feedback_disputes/YYYY-MM-DD.jsonl` so we can audit AI miscalls. See
  EPIC-10.

### 10. Deployment

- **Default working assumption:** single Docker container on a VPS, deployed
  via SSH + ansible (mirroring `vps_management` patterns). One service in
  `docker-compose.yml`. `verify.sh` confirms the container is up and the
  bot answers `/start`.
- **Blocks:** A future deployment epic (post-MVP foundation).

### 11. Web UI (deferred)

Per PRD §6 P0.5, a lightweight web UI is allowed in MVP. EPIC-15 is marked
**Deferred** — re-evaluate after 4–6 weeks of real bot usage. Adding auth +
hosting + framework + CSP early creates a second project inside the first.
In-Telegram editing via inline keyboards covers ~90% of management needs.

## Container shape (working assumption)

When `docker-compose.yml` lands, expect roughly:

```yaml
services:
  fluentloop:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import os; assert os.path.exists('/app/data/fluentloop.sqlite')"]
      interval: 60s
      timeout: 5s
      retries: 3
```

No public ports — the bot polls Telegram (long polling), no inbound webhook.

## Data model overview

The data model in PRD §24 is the source of truth. Key entities:

- `User` — single row, but the column exists for forward-compat.
- `SourceMaterial` + `ExtractedCandidate` — the upload-and-approve pipeline.
- `LearningItem` — words, expressions, grammar rules, mistake patterns.
- `GrammarConcept` — graph (parent/child) for grammar topics.
- `MistakeEvent` + `MistakePattern` — the mistake-as-training loop.
- `ReviewState` — spaced-repetition bookkeeping per learning item.
- `PracticeSession` + `PracticeAttempt` — what happened during practice.

## TODOs to come back to

- [ ] Decide ADR-0002 (Telegram lib).
- [ ] Decide ADR-0003 (model tiering).
- [ ] Decide ADR-0004 (pre-generation).
- [ ] Add a redact-list mechanism for sending lesson notes to AI providers
      (P1 — see [`../SECURITY.md`](../SECURITY.md)).
- [ ] Wire up `verify.sh` once the container exists.
- [ ] Off-VPS backup strategy (P1).
