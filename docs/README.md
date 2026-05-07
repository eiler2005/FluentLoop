# Documentation index

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Tech architecture: framework, libraries, DB, scheduler, AI provider, deployment. **Stub for now** — filled in after ADRs 0002–0004 are decided. |
| [`adr/`](adr/) | Architecture decision records. Each captures one significant choice. |
| [`adr/0001-template.md`](adr/0001-template.md) | Reusable ADR template. |
| [`adr/0002-telegram-library-choice.md`](adr/0002-telegram-library-choice.md) | Stub: choose between `aiogram` and `python-telegram-bot`. |
| [`adr/0003-ai-model-tiering-and-cost.md`](adr/0003-ai-model-tiering-and-cost.md) | Stub: two-tier model strategy (light vs heavy) and cost envelope. |
| [`adr/0004-exercise-pre-generation-strategy.md`](adr/0004-exercise-pre-generation-strategy.md) | Stub: morning batch pre-generation of the day's session. |
| [`features/`](features/) | 15 epic files, one per PRD §28 backlog item. |
| [`features/README.md`](features/README.md) | Epic index, dependency graph, suggested order. |
| [`runbooks/`](runbooks/) | Operational procedures: deploy, demo data, backups, secret handling. |
| [`runbooks/secrets-management.md`](runbooks/secrets-management.md) | Public-git secret and confidential-data handling. |

## How to read these docs

- The [`PRD.md`](../PRD.md) at the repo root is the *what*: product
  requirements, user scenarios, acceptance criteria.
- [`architecture.md`](architecture.md) + ADRs are the *how*: which
  framework, which DB, which AI model, which deployment pattern.
- [`features/`](features/) bridges the two: each epic file maps a chunk of
  the PRD onto a concrete unit of work with its own acceptance criteria
  and verification plan.
