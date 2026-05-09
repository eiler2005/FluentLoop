# FluentLoop

Personal Telegram bot for English learning. B2+/C1- focus, business and IT
context, text-only MVP, single Docker container on a VPS.

> **Status:** MVP learning-engine slice — EPIC-01 through EPIC-14 and
> EPIC-16 through EPIC-21 have compact code paths and tests; EPIC-15 remains
> deferred.

## What it does (intended MVP)

A daily ~15-minute English practice loop in Telegram, driven by the user's
own lesson materials:

1. User uploads lesson notes, expressions, teacher feedback.
2. Bot extracts a lesson title/theme/focus, knowledge areas, words /
   expressions / grammar rules / mistake risks, and asks for approval before
   saving new active items.
3. Bot stores approved items, links them to a reusable lesson plan, indexes
   local material chunks, and schedules items for spaced repetition.
4. Once a day, bot generates a 15-minute session of about 15-20 micro-drills
   from active lesson plans, due items, weak items, mistake patterns, grammar
   concepts, and recent material.
5. User can browse lesson topics, inspect lesson cards, or explicitly start a
   random/topic lesson in Telegram.
6. Bot checks answers, gives compact teacher feedback, can show detailed
   stored explanations, supports `/skip`, logs mistakes, and updates progress.
7. Recurring mistakes turn into mistake patterns and re-appear in future
   practice.

Full product specification: [`PRD.md`](PRD.md).

## Documentation map

| File | Purpose |
|---|---|
| [`PRD.md`](PRD.md) | Product requirements (the *what*). |
| [`AGENTS.md`](AGENTS.md) | Durable rules for any AI agent in this repo. |
| [`CLAUDE.md`](CLAUDE.md) | Thin Claude Code entrypoint, imports `AGENTS.md`. |
| [`SECURITY.md`](SECURITY.md) | Threat model, secrets policy, third-party data flow. |
| [`docs/architecture.md`](docs/architecture.md) | Tech architecture (the *how*), including Telegram, SQLite, scheduler, AI providers, deployment shape. |
| [`docs/adr/`](docs/adr/) | Architecture decision records. |
| [`docs/features/`](docs/features/) | 21 epic files: original MVP backlog plus learning-engine roadmap. |
| [`docs/runbooks/`](docs/runbooks/) | Operational procedures: deploy, demo data, backups, secret handling. |

## Repository layout

```
FluentLoop/
├── PRD.md                  Product requirements.
├── README.md               You are here.
├── AGENTS.md               Durable rules for AI agents.
├── CLAUDE.md               Claude Code entrypoint.
├── SECURITY.md             Threat model + privacy disclosure.
├── .env.example            Environment template.
├── .gitignore
├── .claude/settings.json   Permissions for Claude Code in this project.
├── docs/
│   ├── README.md
│   ├── architecture.md     Tech architecture.
│   ├── adr/                Architecture decision records.
│   ├── features/           21 epic files.
│   └── runbooks/
├── scripts/                Deploy, smoke, seed, and operational helpers.
├── src/                    Python package (`fluentloop`).
└── tests/                  Pytest suite.
```

## Current implementation map

The original bot foundation is in place, and the learning-engine roadmap is
implemented as the current practice path:

- EPIC-16: `/today` uses a staged Learning Engine with dynamic `Step X/N`.
- EPIC-17: uploaded materials can become reusable `LessonPlan` pools.
- EPIC-18: LLM calls are centralized behind the DeepSeek gateway with fallback.
- EPIC-19: high-value writing, grammar, and business prompts can be AI-enhanced.
- EPIC-20: grammar concepts are practical business/IT micro-skills.
- EPIC-21: uploaded materials are indexed into local chunks for lightweight
  context search.
- Lesson navigation: `/topics`, `/lessons [query]`, `/lesson <id>`,
  `/lesson random`, `/lesson topic <query>`, plus `/practice vocab|grammar|mistakes|writing|review|mixed`.
- Seed catalog: `scripts/seed_b2_curriculum.py` creates 20 deterministic
  B2/B2+ business/IT lesson plans without DeepSeek and exports
  `docs/curriculum/b2_b2plus_lesson_catalog.md`.

See [`docs/features/README.md`](docs/features/README.md) for the full graph.

## MVP success criteria

Lifted from PRD §26 — the bot is "done enough" when:

1. User can upload text materials after a lesson.
2. Bot extracts a lesson overview, knowledge areas, words, expressions, rules,
   and mistake risks.
3. User approves what becomes active learning items.
4. Approved material becomes a reusable lesson pool.
5. Bot generates a daily 15-minute practice session automatically.
6. User completes 15-20 micro-drills in Telegram.
7. User can skip a drill and see the correct answer with a short explanation.
8. Bot checks answers and explains mistakes in a teacher-like way.
9. Recurring mistakes become mistake patterns and surface in future practice.
10. Spaced repetition schedules due items correctly.
11. User can view basic progress.

Voice, web UI, multi-user, generic content import are explicitly **not** MVP
goals.
