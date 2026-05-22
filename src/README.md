# src/

Application source code for the FluentLoop Telegram bot.

```text
src/fluentloop/
├── __main__.py          Entrypoint: `python -m fluentloop`.
├── bot/                 Telegram routing, handlers, state, workspace replies.
├── ai/                  Provider abstraction and deterministic fallback.
├── llm/                 DeepSeek gateway, schemas, prompts, task routing.
├── db/                  SQLAlchemy models and session helpers.
├── practice.py          Session lifecycle and answer/skip handling.
├── learning_engine.py   Daily and lesson-mode exercise composition.
├── lesson_plans.py      User-owned lesson plan pools and lesson browser logic.
├── lesson_library.py    EPIC-23 shared seed templates and subscription clones.
├── curriculum_b2.py     Deterministic B2/B2+ seed catalog.
├── curriculum_chunks.py Owner-generated chunk JSONL validation/import.
├── lesson_formats.py    EPIC-22 lesson formats and operational drills.
├── feedback.py          Answer feedback, native rewrite, layered details.
├── srs.py               Review intervals, including sub-day GIR.
├── mistakes.py          Mistake events and pattern detection.
└── materials.py         Upload storage and material chunking.
```

Keep user-facing behavior documented in `../docs/user-guide.md` and
`../docs/material-upload-guide.md`; keep implementation scope in
`../docs/features/`.
