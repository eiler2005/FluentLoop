# src/

Application source code (Python). Empty until [EPIC-01](../docs/features/EPIC-01-bot-foundation.md) starts.

Expected layout once EPIC-01 lands:

```
src/fluentloop/
├── __init__.py
├── __main__.py        Entrypoint: `python -m fluentloop`.
├── bot/               Telegram handlers (per ADR-0002).
├── ai/                AI provider abstraction (per ADR-0003).
├── db/                SQLAlchemy models, Alembic migrations.
├── srs.py             Spaced-repetition algorithm (EPIC-06).
├── practice/          Session generation (EPIC-07) + serving (EPIC-08).
├── exercises/         Exercise type registry (EPIC-09).
├── prompts/           AI prompt templates.
└── seeds/             Seed data (e.g. grammar concepts).
```
