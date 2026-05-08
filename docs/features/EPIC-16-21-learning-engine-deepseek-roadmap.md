# EPIC-16..21 — Learning engine and DeepSeek roadmap

**Status:** Done
**Source:** Codex implementation roadmap imported 2026-05-08.

## Goal

Turn FluentLoop's daily practice from a flat batch of exercises into a
structured 15-minute Telegram lesson loop, while keeping the MVP lightweight:
one Docker container, SQLite, local file storage, scheduler, Telegram bot, and
a small DeepSeek gateway. No voice, no web UI, no LangChain, and no external
vector database.

## Implementation sequence

1. **EPIC-16 — Learning Engine v1.** Refactor `/today` into staged practice:
   warmup, input/noticing, controlled practice, grammar or mistake focus, free
   production, recap. The live target is 15-20 micro-drills inside a
   15-minute session, with dynamic `Step X/N`.
2. **EPIC-17 — Persistent LessonPlan v1.** Add `LessonPlan`, `LessonStep`, and
   `LessonPlanItem`, linked to existing `SourceMaterial` and `LearningItem`
   rows.
3. **EPIC-18 — DeepSeek LLM Gateway v1.** Centralize DeepSeek calls through a
   small JSON-validating gateway with task-aware Pro/Flash routing and
   deterministic fallback.
4. **EPIC-19 — AI Exercise Generator v1.** Use the gateway for high-value
   exercise stages where deterministic templates are weak.
5. **EPIC-20 — Grammar Brain v1.** Expand grammar into practical business/IT
   micro-skills linked to items and mistake patterns.
6. **EPIC-21 — Light Material Context Search v1.** Split uploaded materials
   into local chunks and search them without external RAG infrastructure.

## Working rules

- Implement one stage at a time.
- Preserve existing `PracticeSession`, `PracticeAttempt`, answer checking, SRS,
  mistake pattern, and Telegram flow behavior.
- Update relevant docs and tests for every stage.
- Before live schema changes, create and verify a SQLite backup.
- Deploy with the existing repository deployment method, run live smoke
  validation, and commit only after tests plus live validation pass.
- Do not push to remote unless explicitly requested.

## Latest product decisions

- Uploaded lesson material should produce a teacher-style lesson overview:
  title, theme, communicative goal, language focus, knowledge areas, and full
  candidate list where Telegram message limits allow it.
- Approval creates a reusable lesson pool; `/today` should prefer active
  lesson plans and supersede stale legacy daily sessions when needed.
- Lesson planning and substantial extraction use the stronger DeepSeek planner
  profile first; high-frequency answer checking and most exercise generation
  use the fast profile. Both paths keep deterministic fallback.
- Answer feedback is layered: compact correction immediately, detailed stored
  explanation via `/feedback explain <attempt_id>` or the teacher-details
  button.
- Practice supports `/skip` and inline `Skip / show answer`; skipped attempts
  reveal the correct answer, advance the session, and do not create mistake
  events.
- Material upload replies should stay in the Materials Upload topic to avoid
  forcing the user to switch chats.
