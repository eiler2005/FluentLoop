# Changelog

All notable changes to FluentLoop are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- EPIC-25 daily vocabulary loop: three short pushes a day in the learner's own
  timezone (morning cards, midday drill, evening quiz), an explicit `graduated`
  state for mastered items, `/setup` onboarding wizard with topic and
  vocabulary presets, a 164-entry starter word bank shipped in the repo, adding
  your own words by plain message, and `/words`, `/more`, `/learned`,
  `/delete`, `/pause`, `/resume`, `/setup`, `/today <n>`.
- `/help` now explains the daily loop: the three slots with their times, how to
  answer each, the English-prompt/Russian-after rule, the interval ladder and
  graduation, and how to add your own words.
- After the evening quiz the bot explains the three rejected options with their
  meanings, in English and Russian.
- Bare `/today` now asks whether you want words or a lesson; `/cards [n]` is
  the direct command for cards.
- A persistent keyboard (Cards, Review, Lesson, My words, Add words) installed
  by `/start`, so practice is one tap from anywhere in the chat.
- The 13 `/practice` modes are grouped into Words, Grammar and mistakes, and
  Writing and speaking.
- `scripts/spread_due_dates.py` deals a seeded backlog of overdue reviews out
  over N days instead of leaving it as one wall.
- The evening quiz is a multi-question set rather than a single question: one
  `vocab_deliveries` row per question, an intro stating the count and
  estimated minutes, the next question after each answer, and a wrap-up score
  on the last. Size is 5/10/15/20 in `/settings`, default 10.
- `/quiz` starts or resumes today's quiz on demand, under its own slot so it
  never consumes the scheduled evening delivery. `/stop` clears pending
  captures and abandons the practice session, reporting any paused quiz
  questions rather than claiming nothing is pending.
- `🎯 Quiz` and `⏹ Stop` joined the persistent keyboard.
- Cards now carry form, meaning and use: the phrase, a Russian translation, the
  English gloss, and an example containing the phrase. Missing pieces are
  generated once per item and never overwrite curated content; newly added
  words are enriched at add time and the confirmation shows the finished card.
  `scripts/enrich_word_cards.py` backfills an existing base. The composition
  rules are written down as EPIC-25 §4a and asserted by the consistency suite.
- Examples that were really generation prompts ("Use 'x' in a realistic tech
  workplace sentence") are recognised, hidden, and replaced.
- The keyboard collapses after each tap and lays out three buttons per row, so
  it no longer occupies half a phone screen. `/keyboard` removes it entirely
  and restores it; the hide message lists the commands that still work.
- Native Telegram quiz polls over Telethon raw API, with an inline-button
  fallback and a `VOCAB_QUIZ_POLLS` kill switch (ADR-0011).
- Qwen as a selectable LLM provider alongside OpenAI and DeepSeek, behind the
  existing `AI_PROVIDER` switch (ADR-0010).

### Fixed
- Prompts handed the model a JSON Schema, and Qwen answered with the schema's
  own envelope, so every generated card parsed as empty. Prompts now list the
  fields plainly; the gateway unwraps a nested answer as a safety net.
- Tests could reach the live LLM with the real API key when they forgot to
  pass their own Settings. conftest now blocks the ambient `.env`.
- Practice replies were routed to the forum workspace regardless of where the
  request came from, so a button tapped in a private chat produced nothing
  visible. Replies now follow the request; broadcasts still address the
  workspace (ADR-0005 amendment).
- `/review` ran the same 16-step template as a lesson, making the two
  indistinguishable. It is now a six-step pass.
- Reading the cards was a dead end with no way to practise them.
- Slot claim rolled back the whole tick: `claim_slot` used
  `session.rollback()` on a duplicate, which discarded every delivery row
  already written in that tick, so a slot whose message had been sent was
  re-delivered every minute. Now uses a SAVEPOINT.
- Native quiz polls were rejected at serialisation: Telethon requires
  `solution` and `solution_entities` to be both set or both absent, and only
  checks in `_bytes()`. Every evening poll silently fell back to buttons.
- Quizzes could offer two defensible answers: distractor ranking preferred
  candidates sharing tags, which pulled in synonyms. Tag preference is now
  inverted and near-synonymous glosses are excluded.
- Prompts mixed languages when an item stored its Russian gloss in `meaning`.
  Cards and questions now take the English gloss; Russian appears after the
  answer.
- The daily tick tried to message seed and demo accounts the command handlers
  reject, producing a failed delivery and a traceback per slot per day.
- `scripts/deploy.sh` never pruned its `pre-migration-*.sqlite` snapshots;
  `BACKUP_RETENTION_DAYS` only covers the scheduled `db-*.sqlite` files.
- `send_reminders` and `run_pre_generation` computed dates in UTC while
  `PracticeSession.target_date_local` is written in the user's timezone, so a
  non-UTC learner could be nudged during an active session.
- Scheduler jobs were registered as `lambda: asyncio.create_task(...)`, which
  dropped the task reference and swallowed exceptions. They are now coroutine
  functions passed directly to APScheduler.
- `User.timezone` and `User.reminder_time` were stored and validated but never
  read by the scheduler; per-user slot timing makes them load-bearing.

### Added (earlier)
- Public-release polish: `LICENSE` (MIT), `CHANGELOG.md`, `CONTRIBUTING.md`.
- README rewrite with badges, ASCII architecture diagram, sample session, and
  roadmap table aimed at portfolio readers.
- ASCII component and data-flow diagrams in `docs/architecture.md`.
- Expanded `tests/README.md` with coverage map, patterns, and CI gate.
- Build-log archive at `docs/build-log/` preserving the autonomous overnight
  session brief, morning report, and deferred questions.
- EPIC-22 foundation: layered feedback buttons, Russian L1 hit detection,
  Pimsleur-style sub-day SRS intervals, confidence ratings, reflection logging,
  evaluation probe scaffolding, chunk JSONL import, and named breakthrough
  practice mode entrypoints.
- EPIC-22 Sprint 2 lesson-format core: Notebook native-diff mining, Discourse
  scoring metadata, Critical Reading tasks, Vocabulary Lab metadata grouping,
  Writing Workshop stages, and Mistake Drill extinction-state metadata.
- EPIC-22 Sprint 3 curriculum: static 10-genre seed catalog and
  `scripts/seed_genre_curriculum.py` for owner-curated genre lessons.
- EPIC-22 Sprint 4 teacher layer: structured Lesson Director decision,
  Coach Journal markdown output, scenario-card selection, and Hint Ladder for
  high-confidence mistake patterns.
- EPIC-22 Sprint 5 operational utility: structured Pre-Meeting Brief,
  Article Lab v1, Debate, Translation Lab, and 4-3-2 Fluency drill cards.
- EPIC-22 Sprint 6 polish: 30-day Article Lab pipeline, `/practice sprint`,
  Rolling Native Comparison in Coach Journal, and richer Why layer context.
- Bilingual learner guide with the FluentLoop learning methodology, visual
  lesson-flow map, method map, training-scope map, first-week onboarding, and
  real learner examples.
- EPIC-23 shared lesson library: `/library`, `/subscribe`, owner-only
  `/publish`, seed catalog template publishing, and per-user subscription
  clones with isolated progress.
- Learner-facing material upload guide with upload-ready templates, good/bad
  examples, and an external LLM prompt for preparing raw notes.
- EPIC-24 learning outcomes loop: `/baseline`, `/outcomes`, `evaluation_runs`,
  `learning_metric_snapshots`, held-out retention, productive chunk usage,
  writing/L1 metrics, mistake extinction, and Article Lab probe tracking.
- Learner-facing `docs/learning-plans.md` with first-week, 30-day, and 12-week
  plans built around the measurable FluentLoop loops.
- Unified lesson type registry and generated public catalog export:
  lesson types, B2/B2+ seed lessons, English for Tech, and 40 scenario cards
  now render to Markdown/HTML under `docs/lesson-catalog/`.
- Docker image packaging now includes `alembic.ini` so deploy-time migrations
  can run inside the container.

### Changed
- EPIC-22 Phase 2 validation is closed: in-session GIR re-fire, negative-path
  tests, migration roundtrip verification, deploy runbook coverage, VPS schema
  verification, and live smoke are now part of the Done evidence.
- Telegram `/help` and workspace help now distinguish the user's personal
  lesson base from the shared B2/B2+ seed library.
- Documentation index, testing guide, runbooks, source map, and agent rules now
  reflect EPIC-24, ADR-0008, 20 test modules, and the current shared-library
  deployment model.
- Coach Journal can include the latest `/outcomes` summary, making the teacher
  loop measurement-aware after the user has run an outcome report.
- EPIC-24 is now marked deployed and smoke validated in the feature index and
  roadmap docs.
- `/lesson` and `/library` now show lesson type and target-mix context so users
  understand what each lesson trains before starting.
- `AGENTS.md` updated to reflect the current epic set and docs tree.
- `docs/architecture.md` upgraded from v0.1 stub framing to v0.2 with all
  ADRs (0002-0008) Accepted referenced.

## [0.1.0] — 2026-05-07

First end-to-end MVP. Personal Telegram bot for B2+/C1- English practice with
a 15-minute daily session driven by the user's own lesson notes. Shipped over
a single autonomous overnight build session — see
[`docs/build-log/`](docs/build-log/) for the verbatim record.

### Added — MVP foundation (EPIC-01..14)
- **EPIC-01** Telethon bot in bot mode, `/start`, `/help`, `/howto`,
  single-allowed-user gate, structured logging with token masking.
- **EPIC-02** User profile and `/settings` (level, focus area, timezone,
  reminder time) with inline keyboard presets and free-text fallback.
- **EPIC-03** `/upload` flow for plain-text and document materials with
  size/format validation and friendly errors.
- **EPIC-04** AI extraction of lesson title/theme/focus + candidate words,
  expressions, rules, mistake risks; one-by-one and approve-all candidate
  review with a per-candidate edit flow.
- **EPIC-05** LearningItem CRUD: add/list/archive/suspend/restore, duplicate
  detection, status transitions exposed as Telegram commands and inline
  buttons.
- **EPIC-06** Spaced repetition with Again/Hard/Good/Easy intervals and a
  due queue; 7-day Good interval audit.
- **EPIC-07** Daily session composer (due + weak + favorites + mistake
  patterns + lesson plans) with overnight pre-generation at 03:00 user-local.
- **EPIC-08** `/today`, daily reminder cron, session resume, daily SQLite
  backups (14-day retention), Telegram forum-topic routing for practice,
  feedback, next-prompts, and summaries.
- **EPIC-09** Six exercise types: guess, translate, cloze, rewrite, error
  correction, follow-up — each with template and metadata registry.
- **EPIC-10** AI judging with structured layered teacher feedback, user
  override (`Hard` button on a `Good` answer), `/dispute` command writing
  to JSONL, suggested new candidates routed back to the EPIC-04 approval
  queue.
- **EPIC-11** MistakeEvent log; `MistakePattern` auto-created with
  `confidence=low` after ≥3 similar events in 14 days; user-confirmed
  promotion to `confidence=high`; pattern examples viewable before
  focus/ignore.
- **EPIC-12** Grammar concept graph with parent/child links and rule
  refresher selection.
- **EPIC-13** `/stats` and weekly digest job, scheduled and split for
  Telegram message limits.
- **EPIC-14** `/favorites` toggle, 20-item cap, prioritization in daily
  generation.
- **EPIC-15** Web UI — explicitly **deferred**, re-evaluate after 4–6 weeks
  of bot use.

### Added — Learning-engine roadmap (EPIC-16..21)
- **EPIC-16** Staged Learning Engine: `/today` runs a dynamic
  `Step X / N` flow over 15–20 micro-drills.
- **EPIC-17** Persistent `LessonPlan` pools, lesson browser commands
  (`/topics`, `/lessons`, `/lesson <id>`, `/lesson random`,
  `/lesson topic <q>`), and a deterministic B2/B2+ business/IT curriculum
  seed (`scripts/seed_b2_curriculum.py`).
- **EPIC-18** Centralized DeepSeek LLM gateway with task-aware Pro/Flash
  routing, JSON contract, bounded timeouts, and deterministic fallback.
- **EPIC-19** Selective AI-generated high-value exercise prompts (writing,
  grammar, business) with deterministic guardrails.
- **EPIC-20** Practical business/IT grammar concepts and knowledge areas
  surfaced in practice as compact micro-skills.
- **EPIC-21** Local material chunking and lightweight keyword retrieval
  for context-aware practice.

### Operations
- Single Docker container (`python:3.11-slim`); `docker-compose.yml`
  mounts `./data:/app/data` for SQLite, sessions, backups, and disputes.
- APScheduler in-process for daily reminder, 03:00 pre-gen, 04:00 SQLite
  backup with 14-day rotation.
- `scripts/deploy.sh`: rsync code + `.env` (mode 600) to the VPS, then
  `docker compose up -d --build`, log tail, smoke test.
- `scripts/telegram_workspace_maintenance.py`: post-deploy `setMyCommands`
  sync, Help-topic refresh and pin, safe deletion of bot-authored stale
  help/smoke messages.

### Quality
- 16 test modules, ~36 tests passing; `ruff` + `pytest` green in
  GitHub Actions on every push.
- `scripts/secret_scan.py` runs in CI and as a pre-commit hook.
- `secrets/` catalog convention for local confidential data; `.env` and
  `secrets/` are gitignored.

[0.1.0]: https://github.com/eiler2005/FluentLoop/releases/tag/v0.1.0
[Unreleased]: https://github.com/eiler2005/FluentLoop/compare/v0.1.0...HEAD
