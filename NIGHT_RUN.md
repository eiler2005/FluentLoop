# NIGHT_RUN — Autonomous Codex brief

**Read this top-to-bottom. Then start.** This file is your single source of
truth for the unsupervised overnight session. The user is asleep and will
not respond to questions until morning.

> **Never paste credentials into NIGHT_QUESTIONS.md or MORNING_REPORT.md.**
> Both files are committed to git. Token-shaped strings, API keys, real
> Telegram user IDs — all forbidden from these files. If you need to
> reference a credential, write `<TELEGRAM_BOT_TOKEN>` etc. as a
> placeholder.

---

## 1. Mission

You are Codex, working unsupervised on the FluentLoop project at
`/Users/DenisErmilov/FluentLoop`. The product is a personal Telegram bot
for English learning (B2+/C1, business/IT focus). Background: read
`PRD.md`, `AGENTS.md`, `docs/architecture.md`, `docs/adr/0002`, `0003`,
`0004`. They are short and load-bearing.

**Tonight's goal:** ship as many of the 15 epics as you can, in the order
listed in §5 below, with code + tests + docs + commits + VPS deploys when
appropriate. Target: 10–11 epics. Mandatory floor: EPIC-01, 02, 05.

**Morning deliverable:** `MORNING_REPORT.md` filled in (template already
exists). Optional: `NIGHT_QUESTIONS.md` with anything you couldn't decide.

---

## 2. Identity & permissions for tonight

`AGENTS.md` says "never commit/push/deploy without explicit user
permission." That rule is **explicitly overridden** by this file for the
allowed actions below — and only those.

### Allowed

- Read and write any file under `/Users/DenisErmilov/FluentLoop/`.
- Install Python packages into the project venv
  (`.venv/`, gitignored).
- Run `pytest`, `ruff`, `mypy`, `alembic` locally.
- `docker build`, `docker compose up/down/logs/ps` on local Docker
  Desktop.
- Commit incrementally to `main`. Use the commit message format in §6.
- Deploy to the user's VPS via `scripts/deploy.sh` (which mirrors the
  openclaw rsync+ssh pattern).
- SSH to the VPS for **read-only** diagnostics:
  `docker ps`, `docker compose logs`, `df -h`, `free -m`, `uptime`,
  `cat /opt/fluentloop-bot/data/...` (your own service only).

### Forbidden

- `git push --force` anywhere.
- `git reset --hard` more than one commit deep.
- `git rebase -i` or interactive git anything.
- `rm -rf` on `data/`, `secrets/`, `.git/`, or anything outside
  `/Users/DenisErmilov/FluentLoop/`.
- `sudo` on the local Mac.
- Touching `~/.ssh/`, `~/.aws/`, `~/.kube/`, or any user dotfile.
- Modifying any file under
  `/Users/DenisErmilov/aiprojects/openclaw_firststeps/`,
  `/Users/DenisErmilov/aiprojects/vps_management/`,
  `/Users/DenisErmilov/aiprojects/router_configuration/` —
  these are read-only references.
- Editing `AGENTS.md`, `CLAUDE.md`, `PRD.md`, or any Accepted ADR
  without first writing your concern to `NIGHT_QUESTIONS.md`.
- Spending more than **$10** of OpenAI API credit (see §8).

### VPS specifics

You may operate on **only** the FluentLoop service on the VPS:

- `cd /opt/fluentloop-bot && docker compose up -d --build`
- `cd /opt/fluentloop-bot && docker compose down`
- `cd /opt/fluentloop-bot && docker compose logs --tail=N`
- `cd /opt/fluentloop-bot && docker compose pull`
- `docker volume prune` is NOT allowed (would affect other services).

You may NOT:

- `docker rm` or `docker rmi` of containers/images you didn't create.
- `apt`, `apt-get`, `yum`, `snap`, or any package manager.
- `sudo` anywhere on the VPS.
- Touch `/opt/openclaw/`, `/opt/telethon-digest/`, or any other service
  directory under `/opt/`.

---

## 3. Reference projects (when stuck on a pattern)

These three repos under `/Users/DenisErmilov/aiprojects/` are read-only
for you. Consult them when stuck:

- **Telethon bot patterns + Docker shape:**
  `openclaw_firststeps/artifacts/telethon-digest/{Dockerfile,docker-compose.yml,requirements.txt,reader.py,poster.py,auth.py,cron-digest.sh}`.
  Note: their Telethon runs as a user account (not bot mode). You're
  using bot mode — adapt `auth.py` accordingly:
  `client.start(bot_token=os.environ['TELEGRAM_BOT_TOKEN'])`.
- **Deploy script template:**
  `openclaw_firststeps/scripts/deploy-telethon-digest.sh`. Your
  `scripts/deploy.sh` is already adapted from this. If it breaks,
  consult the original.
- **VPS access conventions, ansible inventory, vault, verify pattern:**
  `vps_management/{ansible/inventory/production.yml,ansible/playbooks/99-verify.yml,verify.sh}`.
- **Repo structure / AGENTS.md style:**
  `router_configuration/{AGENTS.md,docs/,SECURITY.md}` (already lifted in
  scaffolding).

Read these; never copy verbatim; always adapt.

---

## 4. Pre-flight (mandatory; abort if any fails)

Run in order. If any returns non-zero, **stop entirely**. Append the
exact failure output to `NIGHT_QUESTIONS.md` and exit. Do NOT attempt to
edit `.env` yourself — that's the user's job.

```bash
cd /Users/DenisErmilov/FluentLoop
python scripts/check_env.py        # all required keys present + non-empty
python scripts/check_telegram.py   # Telethon bot mode handshake OK
python scripts/check_openai.py     # OpenAI minimal call OK (~$0.0001)
bash scripts/check_vps.sh          # SSH + Docker on VPS OK
```

All four must exit 0 before you write any code.

---

## 5. Epic execution order

Work strictly in this order. Skip an epic only if you get **stuck** per
§7; don't reorder for convenience.

**Mandatory floor** (must land or session counts as failure):

1. **EPIC-01** Bot foundation
2. **EPIC-02** User profile + `/settings`
3. **EPIC-05** Learning items CRUD + `/add`

**High-priority core** — the end-to-end loop without AI:

4. **EPIC-06** Spaced repetition
5. **EPIC-09** Exercise types registry
6. **EPIC-08** Daily practice in Telegram (initially serves
   hand-seeded exercises until EPIC-07 lands)
7. **EPIC-03** Material upload (no AI yet)

**AI-dependent** — counts against $10 cap; do only if budget allows:

8. **EPIC-04** AI extraction + approval
9. **EPIC-10** Answer checking + feedback

**Stretch** — in this order if time remains:

10. **EPIC-11** Mistake events + patterns
11. **EPIC-07** Auto practice generation (replaces hand-seeded path
    in EPIC-08)
12. **EPIC-13** Stats + weekly summary
13. **EPIC-14** Favorites
14. **EPIC-12** Grammar concepts graph

**Deferred** — do not start:

- **EPIC-15** Web UI (status: Deferred per ADR).

---

## 6. Per-epic protocol

For each epic, follow this exact sequence:

1. Read `docs/features/EPIC-NN-*.md` end to end.
2. Update epic file's `Status:` line to
   `In progress (YYYY-MM-DD HH:MM UTC)`.
3. Plan the work in your head. Don't write a separate plan doc.
4. Implement: code under `src/fluentloop/`, tests under `tests/`,
   Alembic migration if you change the schema.
5. Run lint and tests:
   ```bash
   ruff check src tests && pytest -q
   ```
   Both must pass.
6. **If tests fail:** try to fix. Up to 3 attempts on the same
   approach. If still red after 3, write to `NIGHT_QUESTIONS.md` per
   §7 and skip to the next epic. Revert your local changes if needed
   (`git checkout -- src tests`).
7. Update the epic file: change `Status:` to
   `Done (YYYY-MM-DD HH:MM UTC)`. Append a short
   "## Notes from implementation" section listing anything that diverged
   from the planned approach and *why*.
8. If you made any architectural decision not yet recorded:
   - Either update `docs/architecture.md` if it's a small clarification.
   - Or write a new ADR (`docs/adr/0005-….md`, `0006-…`, etc.) if it's
     significant. Use `docs/adr/0001-template.md` as the format. Mark
     `Status: Accepted` only after you've completed the relevant work.
9. Commit on `main`:
   ```
   EPIC-NN: <one-line summary>

   - <bullet 1>
   - <bullet 2>
   - <bullet 3>

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   ```
   Sign with the same Claude co-author tag for consistency with prior
   commits.
10. **Deploy decision.** After any epic where Telegram-visible behavior
    changed (EPIC-01, 02, 03, 04, 08, 09, 10), run:
    ```bash
    bash scripts/deploy.sh
    python scripts/smoke_telegram.py    # sends /start, expects reply
    ```
    If the smoke test fails: try to fix once. If still broken, roll back
    on the VPS (`ssh <ssh-user>@<vps-host> 'cd /opt/fluentloop-bot &&
    git checkout HEAD~1 docker-compose.yml && docker compose up -d'` —
    or whatever rollback path is cleanest), append failure to
    `NIGHT_QUESTIONS.md`, continue with next epic on local Docker.

---

## 7. Stuck protocol

You're stuck if **any** of these is true:

- 3 consecutive test failures on the same approach.
- A required external service (Telegram, OpenAI, VPS) is unreachable
  for >2 minutes after retry.
- A decision needs to violate an Accepted ADR.
- An epic's acceptance criteria are ambiguous and you'd be guessing.

When stuck, append to `NIGHT_QUESTIONS.md` (create if missing):

```markdown
## NN. <epic NN — short question summary>

**Epic:** EPIC-NN-<slug>.md
**Where:** `<file path>:<line>` or `design-level`
**What's blocked:** <one paragraph>
**Default I would use if forced:** <one sentence>
**Why I'd prefer to ask:** <one sentence>
```

Then **skip to the next epic in §5**. Do not block on a question.

---

## 8. Cost telemetry

Log every OpenAI call to `data/usage_log.jsonl` (append-only):

```json
{"ts":"2026-05-07T02:13:09Z","model":"gpt-4o-mini","prompt_tokens":345,"completion_tokens":89,"task":"epic_04_extract","cost_usd":0.000172}
```

Pricing (embed these constants in `src/fluentloop/ai/cost.py`):

- `gpt-4o-mini`: $0.150 per 1M input tokens, $0.600 per 1M output tokens
- `gpt-4o`: $2.50 per 1M input tokens, $10.00 per 1M output tokens

After every AI epic completes, sum the JSONL costs:

- **At ≥ $5 spent:** log a `WARNING` line to `MORNING_REPORT.md`'s
  "Anomalies" section, switch all heavy-tier (`gpt-4o`) calls to
  light-tier (`gpt-4o-mini`) for the rest of the night.
- **At ≥ $10 spent:** **stop AI work entirely.** Continue with non-AI
  epics if any remain.

Realistic envelope: with 10–11 epics including AI ones, expect
~$3–7 actual spend. The cap is for runaway-loop protection, not for
normal operation.

---

## 9. Morning report format

Before exiting, fill `MORNING_REPORT.md` (template already there).
Required sections:

- **Time:** started / ended (UTC + Moscow).
- **Epics done:** table — `# | epic | commit hash | tests pass? | deployed?`.
- **Epics stuck:** list — `# | epic | link to NIGHT_QUESTIONS.md entry`.
- **Epics not attempted:** list — and why (`out of time` / `blocked by
  upstream stuck epic` / `out of budget`).
- **Total OpenAI spend:** total + per-epic breakdown.
- **Deploys made:** timestamps + commit hashes + smoke-test result.
- **Surprises / anomalies:** one paragraph each (max 5).
- **Recommended morning order of business:** 3 bullets.

Keep it scannable. The user wants to read it in 60 seconds and decide
what to do first.

---

## 10. Defaults for unspecified decisions

Use these without asking. Save your "asks" budget for true ambiguity.

- **Python:** 3.11 (matches openclaw_firststeps).
- **ORM:** SQLAlchemy 2.x with type annotations (`Mapped[...]`).
- **Migrations:** Alembic, autogenerate on schema change.
- **Schemas:** Pydantic 2.x for all AI input/output and FSM state.
- **Test framework:** pytest + pytest-asyncio. Mock OpenAI calls with
  unittest.mock; never hit the real API in unit tests.
- **Lint/format:** ruff (lint + format both).
- **Type check:** mypy with `strict_optional = True`, otherwise lenient.
- **Telegram lib:** Telethon 1.36.0 in bot mode. FSM is your own helper
  in `src/fluentloop/bot/state.py` (per architecture.md §1).
- **OpenAI client:** `openai>=1.40.0`, structured outputs via
  `response_format={"type":"json_schema", ...}`.
- **AI tier choice (per ADR-0003):**
  - `gpt-4o-mini` for routine answer checking, exact-match,
    classification.
  - `gpt-4o` for extraction, grammar feedback, "more natural"
    rewrites, weekly report.
- **Logging:** stdlib `logging` to stdout, INFO level, format includes
  timestamp + module + message. Mask token-shaped strings.
- **Time zones:** all DB timestamps in UTC; convert to user's TZ
  (`User.timezone`) only at display.
- **Default user TZ:** `Europe/Moscow` (matches `.env`).
- **Default reminder time:** `20:00` user TZ.
- **UX strings in chat:** short, professional, en-US tone for English-
  learning prompts; for system messages (errors, settings) — RU is fine
  since the user is L1 Russian.
- **For ambiguous default values (counts, intervals):** see the SRS
  algorithm spec in `docs/features/EPIC-06-spaced-repetition.md`.
- **Retry policy on AI calls:** 1 retry with 1s backoff, then surface
  the error.

---

## 11. Reference data (don't re-discover this)

Pre-loaded into `.env` already (verify with `python scripts/check_env.py`):

- `TELEGRAM_BOT_TOKEN` — bot @fluentloop_ai_bot.
- `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` — Telethon needs these even
  in bot mode (it speaks MTProto).
- `TELEGRAM_ALLOWED_USER_ID` — the only user the bot will respond to.
- `OPENAI_API_KEY` — for the bot's gpt-4o-mini / gpt-4o calls.

VPS facts:

- Host: `<vps-host>` (Hetzner CX23, Ubuntu 24.04).
- SSH: `<ssh-user>@<vps-host> -i ~/.ssh/id_rsa` (BatchMode=yes
  passwordless).
- Docker pre-installed.
- Deploy directory convention: `/opt/<service>/`. Yours:
  `/opt/fluentloop-bot/`.
- Other services on the box you must not touch:
  `/opt/openclaw/`, `/opt/telethon-digest/`.

Container shape (per `docs/architecture.md` §1, §10):

- Base: `python:3.11-slim`.
- Workdir: `/app`.
- `env_file: .env` in `docker-compose.yml`.
- Volume mount: `./data:/app/data` (SQLite, sessions, backups,
  dispute logs).
- `restart: unless-stopped`.
- Long polling (no exposed ports).

---

## 12. Final "I am ready" checklist

Before you write any code, confirm — silently to yourself:

- [ ] I have read this entire file.
- [ ] I have read `AGENTS.md`, `docs/architecture.md`, ADR-0002/3/4.
- [ ] All four pre-flight scripts return 0.
- [ ] I understand which actions are forbidden (§2).
- [ ] I understand the cost cap (§8).
- [ ] I understand the stuck protocol (§7).
- [ ] I will fill `MORNING_REPORT.md` before exiting.

If any box is unchecked: don't proceed. Write to NIGHT_QUESTIONS.md and
stop.

Otherwise: go to §5 and start with EPIC-01.

Good night to the user. Build something good.
