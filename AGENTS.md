# AGENTS.md — Durable rules for AI agents working in this repo

This file is shared by Claude Code, Codex, and any other AI agent working on
FluentLoop. Keep it short and load-bearing — durable rules only, not session
notes.

## Project at a glance

- **Product:** FluentLoop — personal Telegram bot for English learning (B2+/C1-,
  business and IT focus).
- **Interface:** Telegram, text-only. No voice in MVP.
- **Audience:** Single user. No multi-tenancy in MVP.
- **Deployment target:** One Docker container on a VPS.
- **Source of product truth:** [`PRD.md`](PRD.md).
- **Source of implementation truth:** [`docs/features/`](docs/features/) — 21
  epic files. EPIC-01 through EPIC-15 mirror the PRD §28 backlog (EPIC-15 is
  Deferred); EPIC-16 through EPIC-21 are the post-MVP learning-engine roadmap.
  See [`docs/features/README.md`](docs/features/README.md) for the index.
- **Source of architectural truth:** [`docs/architecture.md`](docs/architecture.md)
  + ADRs in [`docs/adr/`](docs/adr/) (0002–0007 all Accepted).
- **Build provenance (history):** [`docs/build-log/`](docs/build-log/) holds the
  autonomous overnight session brief and morning report. Frozen artifacts —
  read for context, do not treat as living documentation.

## Karpathy-style workflow

- **Think before coding.** State assumptions, surface ambiguity, confirm before
  large changes.
- **Read the PRD section and the relevant epic file before writing code.**
- **Smallest useful change.** Don't refactor adjacent code "while you're there".
- **Surgical edits.** Touch only files needed for the task.
- **Match local style.** Existing naming, indentation, doc tone wins.
- **Preserve user work.** Never revert unrelated local edits.
- **Verifiable goals.** Every change ends with a check that proves it works
  (test, manual flow, syntax check, `verify.sh`).
- **Update docs before recommending a commit.** PRD, epic file, ADR, README —
  whichever applies.

## Safety rules — never without explicit user permission

- Never run `git commit`, `git push`, `git reset --hard`, `git clean -f`, or
  `git checkout --` on the user's behalf.
- Never run a deploy command (anything that touches the VPS).
- Never `docker rm`, `docker compose down`, `docker system prune`, or `rm -rf`
  on user data or volumes.
- Never disable or bypass hooks (`--no-verify`, `--no-gpg-sign`).
- Never `apt full-upgrade`, `sudo`, or modify system files outside the
  container.

When in doubt — ask. The cost of confirming is low; the cost of an unwanted
destructive action is high.

## Secrets & privacy

- Real `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` never appear
  in git, in commit messages, in logs, or in agent outputs.
- Only `.env.example` is committed. Real `.env` is gitignored.
- **`secrets/` catalog** (gitignored entirely via `.gitignore:5`) — canonical
  location for confidential data: `secrets/fluentloop.env` is the
  ready-to-copy version of `.env` (preloaded with real values where
  available, placeholders for the rest). Same pattern as
  `aiprojects/openclaw_firststeps/secrets/` per service. Never commit
  anything from `secrets/`. Set mode 600 on all files inside.
- User lesson notes, mistakes, and answers are sensitive — they may contain
  names of colleagues, clients, projects. Treat the contents of `data/` as
  private. See [`SECURITY.md`](SECURITY.md) for the third-party data flow
  disclosure (what gets sent to OpenAI / Anthropic and why).
- Before any commit, scan staged files for `BOT_TOKEN`, `API_KEY`, `sk-`,
  `xoxb-`, real Telegram user IDs, and email addresses. If unsure, ask.

## Architectural invariants

- **PRD §29 stays out of the PRD.** Framework, library, DB, AI provider,
  prompts, deployment — these belong in `docs/architecture.md` and ADRs, not
  in the PRD.
- **Approval is required for adding new active learning items** from uploaded
  materials (PRD §5.1, §5.5, §13). Exercise generation from already-approved
  data is automatic.
- **Mistake patterns are auto-created with `confidence=low` only** after ≥3
  similar mistake events within 14 days. User confirmation promotes them to
  `confidence=high`. See `docs/features/EPIC-11-mistake-events-and-patterns.md`.
- **Single-user.** No auth layer beyond `TELEGRAM_ALLOWED_USER_ID`. The data
  model carries `user_id` for forward-compat only — do not build multi-tenant
  infrastructure.
- **Architectural decisions become ADRs before implementation.** If a task
  forces a decision that will affect future work, write the ADR first.

## Where things live

```
FluentLoop/
├── PRD.md                        Product requirements (verbatim).
├── README.md                     Project overview, quick links.
├── AGENTS.md                     This file. Durable rules.
├── CLAUDE.md                     Thin Claude Code entrypoint, imports AGENTS.md.
├── SECURITY.md                   Threat model, secrets policy, privacy disclosure.
├── CHANGELOG.md                  Versioned release notes.
├── CONTRIBUTING.md               Dev setup, test commands, ADR-first rule.
├── LICENSE                       MIT.
├── .env.example                  Environment template. Never put real values here.
├── .gitignore
├── .pre-commit-config.yaml       Local hooks: secret scan + ruff.
├── .claude/
│   └── settings.json             Permissions for Claude Code in this project.
├── .github/
│   └── workflows/ci.yml          GitHub Actions: secret scan + ruff + pytest.
├── docs/
│   ├── README.md                 Doc index.
│   ├── architecture.md           Tech architecture (Telegram, SQLite, scheduler, AI).
│   ├── testing.md                Standard test gate and what tests cover.
│   ├── adr/                      Architecture decision records (0002–0007 Accepted).
│   ├── features/                 21 epic files (EPIC-15 Deferred; rest Done).
│   ├── runbooks/                 Operational procedures.
│   ├── curriculum/               Generated B2/B2+ lesson catalog.
│   └── build-log/                Autonomous-build journal (frozen history).
├── migrations/                   Alembic schema migrations.
├── scripts/                      Deploy, smoke, seed, and operational helpers.
├── secrets/                      Local-only confidential data (gitignored).
├── data/                         Runtime artifacts: SQLite, sessions, backups (gitignored).
├── src/fluentloop/               Python package — bot, db, ai, llm, learning engine.
├── ansible/                      Deploy playbooks (placeholder for future deployment epic).
└── tests/                        Pytest suite (16 modules, ~36 tests).
```

## Verification commands

Used by agents and humans to confirm a change is safe:

```bash
# Structure & sanity
find . -maxdepth 3 -type f | sort
ls docs/features/EPIC-*.md | wc -l    # 21 epic files + 1 roadmap index = 22

# No secrets staged
python scripts/secret_scan.py
git diff --cached | grep -E '(BOT_TOKEN|API_KEY|sk-[A-Za-z0-9]{20})' && echo "LEAK!" || echo "clean"

# Style and tests
ruff check src tests scripts
pytest -q
```

## Working with the PRD and epic files

- The PRD is the *what*. Epic files are the *how*. Don't duplicate PRD content
  into epic files — link to the relevant section.
- If reality diverges from the PRD (e.g. a constraint forces a change), update
  the PRD first, then the epic, then the code.
- An epic file may be in `Status: Planned`, `In progress`, `Done`, or
  `Deferred`. Update the status when you start or finish work.
- New ideas that don't fit the existing epics → add a P1/P2 entry to PRD §6
  first; only carve out a new epic file once scope is concrete enough to
  estimate.
