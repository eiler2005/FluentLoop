# Architecture Decision Records

Lightweight ADRs. One file per significant decision. Numbered sequentially.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-template.md) | ADR template | Template |
| [0002](0002-telegram-library-choice.md) | Telegram library choice (Telethon bot mode) | Accepted (2026-05-06) |
| [0003](0003-ai-model-tiering-and-cost.md) | AI model tiering and cost (OpenAI gpt-4o-mini + gpt-4o) | Accepted (2026-05-06) |
| [0004](0004-exercise-pre-generation-strategy.md) | Exercise pre-generation strategy (overnight 03:00 user TZ) | Accepted (2026-05-06) |

## Conventions

- One decision per ADR.
- File name: `NNNN-short-kebab-title.md`.
- Status: `Proposed` → `Accepted` → (`Deprecated` | `Superseded by NNNN`).
- Keep ADRs short — one screen if possible.
- Decisions become ADRs *before* implementation. If you find yourself coding
  around a question, stop and write the ADR first.
- Superseding an ADR doesn't delete the old one; mark it `Superseded by NNNN`
  and keep the history.

## Template

See [`0001-template.md`](0001-template.md) and copy it for new entries.
