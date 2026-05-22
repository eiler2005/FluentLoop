# Architecture Decision Records

Lightweight ADRs. One file per significant decision. Numbered sequentially.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-template.md) | ADR template | Template |
| [0002](0002-telegram-library-choice.md) | Telegram library choice (Telethon bot mode) | Accepted (2026-05-06) |
| [0003](0003-ai-model-tiering-and-cost.md) | AI model tiering and cost (OpenAI gpt-4o-mini + gpt-4o) | Accepted (2026-05-06) |
| [0004](0004-exercise-pre-generation-strategy.md) | Exercise pre-generation strategy (overnight 03:00 user TZ) | Accepted (2026-05-06) |
| [0005](0005-forum-workspace-routing.md) | Forum workspace routing (Telethon + Bot API topic sends) | Accepted (2026-05-07) |
| [0006](0006-public-git-secret-hygiene.md) | Public git secret hygiene | Accepted (2026-05-07) |
| [0007](0007-deepseek-llm-gateway.md) | DeepSeek LLM gateway for learning engine roadmap | Accepted (2026-05-08) |
| [0008](0008-shared-lesson-library.md) | Shared lesson library with per-user clones | Accepted (2026-05-21) |

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
