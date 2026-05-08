# Features

Each epic file maps a chunk of [`../../PRD.md`](../../PRD.md) onto a concrete
unit of work. EPIC-01 through EPIC-15 are the original PRD backlog; EPIC-16
through EPIC-21 extend the learning engine with lesson plans, DeepSeek-backed
LLM routing, teacher feedback, grammar brain, and light material context
search.

## Epic index

| # | File | Status | Summary |
|---|---|---|---|
| 01 | [bot-foundation](EPIC-01-bot-foundation.md) | Done | Telegram bot up, `/start`, `/help`, project skeleton. |
| 02 | [user-profile-settings](EPIC-02-user-profile-settings.md) | Done | Profile creation, `/settings`, level/focus/timezone/reminder. |
| 03 | [material-upload](EPIC-03-material-upload.md) | Done | `/upload`, plain text ingestion, source storage. |
| 04 | [ai-extraction-and-approval](EPIC-04-ai-extraction-and-approval.md) | Done | AI extraction → candidates → approval flow in chat. |
| 05 | [learning-items](EPIC-05-learning-items.md) | Done | CRUD for words / expressions / rules / mistakes. |
| 06 | [spaced-repetition](EPIC-06-spaced-repetition.md) | Done | Simple Again/Hard/Good/Easy intervals + due queue. |
| 07 | [automatic-practice-generation](EPIC-07-automatic-practice-generation.md) | Done | Daily session composer + overnight pre-generation. |
| 08 | [daily-practice-telegram](EPIC-08-daily-practice-telegram.md) | Done | `/today`, reminders, session resume, daily backups. |
| 09 | [exercise-types](EPIC-09-exercise-types.md) | Done | Six exercise types from PRD §15. |
| 10 | [answer-checking-feedback](EPIC-10-answer-checking-feedback.md) | Done | AI judging + user override + dispute log. |
| 11 | [mistake-events-and-patterns](EPIC-11-mistake-events-and-patterns.md) | Done | Mistake log, pattern detection (≥3/14d threshold). |
| 12 | [grammar-rules-graph](EPIC-12-grammar-rules-graph.md) | Done | Grammar concepts as a graph with parent/child links. |
| 13 | [stats-and-weekly-summary](EPIC-13-stats-and-weekly-summary.md) | Done | `/stats` + weekly digest. |
| 14 | [favorites](EPIC-14-favorites.md) | Done | `is_favorite` flag and prioritization. |
| 15 | [optional-web-interface](EPIC-15-optional-web-interface.md) | **Deferred** | Re-evaluate after 4–6 weeks of bot usage. |
| 16 | [learning-engine-v1](EPIC-16-learning-engine-v1.md) | Done | Staged `/today` Learning Engine with 15-20 micro-drills. |
| 17 | [persistent-lesson-plans](EPIC-17-persistent-lesson-plans.md) | Done | LessonPlan / LessonStep / LessonPlanItem lesson pools from source materials. |
| 18 | [deepseek-llm-gateway](EPIC-18-deepseek-llm-gateway.md) | Done | Centralized DeepSeek JSON gateway with fallback. |
| 19 | [ai-exercise-generator](EPIC-19-ai-exercise-generator.md) | Done | Selective AI-generated high-value exercise prompts. |
| 20 | [grammar-brain-v1](EPIC-20-grammar-brain-v1.md) | Done | Practical business/IT grammar concepts and knowledge areas in practice. |
| 21 | [light-material-context-search](EPIC-21-light-material-context-search.md) | Done | Local material chunks and keyword retrieval. |

## Dependency graph

```
                EPIC-01 (bot foundation)
                    │
                    ▼
                EPIC-02 (profile / settings)
                    │
                    ▼
                EPIC-05 (learning items CRUD)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   EPIC-06 (SRS)         EPIC-03 (upload)
        │                       │
        ▼                       ▼
   EPIC-09 (exercise        EPIC-04 (AI extract
    types)                   + approval)
        │                       │
        └───────────┬───────────┘
                    ▼
               EPIC-07 (auto practice
               + pre-generation)
                    │
                    ▼
               EPIC-08 (daily practice
               + reminders + backups)
                    │
                    ▼
               EPIC-10 (answer checking
               + feedback + dispute log)
                    │
                    ▼
               EPIC-11 (mistake events
               and patterns)
                    │
                    ▼
               EPIC-12 (grammar graph)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   EPIC-13 (stats)        EPIC-14 (favorites)


   EPIC-15 (web UI) — deferred, not on critical path.

   EPIC-16 → EPIC-17 → EPIC-18 → EPIC-19 → EPIC-20 → EPIC-21
   (learning engine, lesson plans, DeepSeek, AI exercises, grammar brain,
   light material context search)
```

## Suggested implementation order

```
EPIC-01 → EPIC-02 → EPIC-05 → EPIC-06 → EPIC-09 → EPIC-08 → EPIC-07 → EPIC-10
                                              ↓
                                          EPIC-04 ← EPIC-03 (parallelizable)
                                              ↓
                                          EPIC-11 → EPIC-12
                                              ↓
                                          EPIC-13, EPIC-14
                                              ↓
                                          EPIC-15 (deferred)
                                          ↓
              EPIC-16 → EPIC-17 → EPIC-18 → EPIC-19 → EPIC-20 → EPIC-21
```

The order above prioritizes the **end-to-end loop** as early as possible:
get a daily practice session running with hand-seeded data (EPIC-08 + 09),
*then* layer on automatic generation (EPIC-07) and AI feedback (EPIC-10).
That way every later epic adds visible value to a working bot.

## Epic file template

```markdown
# EPIC-NN — Title

**Status:** Planned | In progress | Done | Deferred
**PRD references:** §X.Y, §A.B
**Depends on:** EPIC-…
**Blocks:** EPIC-…

## Goal
One paragraph — what user-visible outcome this epic delivers.

## In scope
- Concrete deliverables.

## Out of scope
- What is explicitly NOT this epic.

## Acceptance criteria
- Adapted from PRD acceptance criteria for this area.

## Open questions
- Architectural decisions still to make (will become ADRs).

## Verification plan
- How to manually test this end-to-end once implemented.
```

## How to update an epic

- When you start work, change `Status: Planned` → `In progress` and add the
  date.
- If a decision turns into an ADR, link it from `Open questions`.
- If the epic grows beyond ~150 lines, split it into sub-epics rather than
  letting one file become a small specification of its own.
- Keep epic content focused on *what* and *acceptance*. Code-level design
  goes into the source itself or into `docs/architecture.md`.
