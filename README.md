# FluentLoop

Personal Telegram bot for English learning. B2+/C1- focus, business and IT
context, text-only MVP, single Docker container on a VPS.

> **Status:** Planning — repository scaffolded, no implementation yet.
> Next deliverable is `docs/architecture.md` filled in, then EPIC-01 starts.

## What it does (intended MVP)

A daily ~15-minute English practice loop in Telegram, driven by the user's
own lesson materials:

1. User uploads lesson notes, expressions, teacher feedback.
2. Bot extracts words / expressions / grammar rules / mistake patterns and
   asks for approval before saving them.
3. Bot stores approved items and schedules them for spaced repetition.
4. Once a day, bot generates a 7-exercise practice session automatically
   from due items, weak items, mistake patterns, and recent material.
5. Bot checks answers, explains mistakes, logs them, and updates progress.
6. Recurring mistakes turn into mistake patterns and re-appear in future
   practice.

Full product specification: [`PRD.md`](PRD.md).

## Documentation map

| File | Purpose |
|---|---|
| [`PRD.md`](PRD.md) | Product requirements (the *what*). |
| [`AGENTS.md`](AGENTS.md) | Durable rules for any AI agent in this repo. |
| [`CLAUDE.md`](CLAUDE.md) | Thin Claude Code entrypoint, imports `AGENTS.md`. |
| [`SECURITY.md`](SECURITY.md) | Threat model, secrets policy, third-party data flow. |
| [`docs/architecture.md`](docs/architecture.md) | Tech architecture (the *how*). Stub until ADR-0002/3/4 land. |
| [`docs/adr/`](docs/adr/) | Architecture decision records. |
| [`docs/features/`](docs/features/) | 15 epics, one per PRD §28 backlog item. |
| [`docs/runbooks/`](docs/runbooks/) | Operational procedures. Placeholder. |

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
│   ├── architecture.md     Tech architecture (stub for now).
│   ├── adr/                ADRs 0001–0004 (templates / stubs).
│   ├── features/           15 epic stubs.
│   └── runbooks/
├── src/                    Empty until EPIC-01.
├── ansible/                Empty until deployment epic.
└── tests/                  Empty until EPIC-01.
```

## Next steps

Implementation order (see [`docs/features/README.md`](docs/features/README.md)
for the full graph):

```
EPIC-01 → EPIC-02 → EPIC-05 → EPIC-06 → EPIC-09 → EPIC-08 → EPIC-07 → EPIC-10
                                              ↓
                                          EPIC-04 ← EPIC-03 (parallelizable)
                                              ↓
                                          EPIC-11 → EPIC-12
                                              ↓
                                          EPIC-13, EPIC-14
                                              ↓
                                          EPIC-15 (deferred — re-evaluate
                                          after 4-6 weeks of real usage)
```

## MVP success criteria

Lifted from PRD §26 — the bot is "done enough" when:

1. User can upload text materials after a lesson.
2. Bot extracts words, expressions, rules, and mistakes.
3. User approves what becomes active learning items.
4. Bot generates a daily 15-minute practice session automatically.
5. User completes the session in Telegram.
6. Bot checks answers and explains mistakes.
7. Recurring mistakes become mistake patterns and surface in future practice.
8. Spaced repetition schedules due items correctly.
9. User can view basic progress.

Voice, web UI, multi-user, generic content import are explicitly **not** MVP
goals.
