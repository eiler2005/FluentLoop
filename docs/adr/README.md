# Architecture Decision Records

Lightweight ADRs. One file per significant decision. Numbered sequentially.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-template.md) | ADR template | Template |
| [0002](0002-telegram-library-choice.md) | Telegram library choice (Telethon bot mode) | Accepted (2026-05-06) |
| [0003](0003-ai-model-tiering-and-cost.md) | AI model tiering and cost (OpenAI gpt-4o-mini + gpt-4o) | Accepted (2026-05-06), amended by 0010 |
| [0004](0004-exercise-pre-generation-strategy.md) | Exercise pre-generation strategy (overnight 03:00 user TZ) | Accepted (2026-05-06), amended by 0012 |
| [0005](0005-forum-workspace-routing.md) | Forum workspace routing (Telethon + Bot API topic sends) | Accepted (2026-05-07), amended 2026-08-17 |
| [0006](0006-public-git-secret-hygiene.md) | Public git secret hygiene | Accepted (2026-05-07) |
| [0007](0007-deepseek-llm-gateway.md) | DeepSeek LLM gateway for learning engine roadmap | Accepted (2026-05-08), amended by 0010 |
| [0008](0008-shared-lesson-library.md) | Shared lesson library with per-user clones | Accepted (2026-05-21) |
| 0009 | *(reserved: admission policy beyond the environment gate)* | Not written |
| [0010](0010-multi-provider-llm-gateway.md) | Multi-provider LLM gateway (Qwen alongside DeepSeek) | Accepted (2026-08-17) |
| [0011](0011-native-telegram-quiz-polls.md) | Native Telegram quiz polls over Telethon raw API | Accepted (2026-08-17) |
| [0012](0012-per-user-slot-dispatcher.md) | Per-user slot dispatcher for the daily vocabulary loop | Accepted (2026-08-17) |

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
