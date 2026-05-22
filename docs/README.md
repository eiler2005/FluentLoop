# Documentation index

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Tech architecture: framework, libraries, DB, scheduler, AI providers, deployment, learning-engine runtime notes. |
| [`user-guide.md`](user-guide.md) | Bilingual learner guide: methodology, daily process, practice modes, process map, and image prompt. |
| [`material-upload-guide.md`](material-upload-guide.md) | User-facing cookbook for preparing lesson notes, feedback, articles, transcripts, and LLM-assisted upload material. |
| [`adr/`](adr/) | Architecture decision records. Each captures one significant choice. |
| [`adr/0001-template.md`](adr/0001-template.md) | Reusable ADR template. |
| [`adr/0002-telegram-library-choice.md`](adr/0002-telegram-library-choice.md) | Accepted Telegram library choice. |
| [`adr/0003-ai-model-tiering-and-cost.md`](adr/0003-ai-model-tiering-and-cost.md) | Accepted two-tier model strategy and cost envelope. |
| [`adr/0004-exercise-pre-generation-strategy.md`](adr/0004-exercise-pre-generation-strategy.md) | Accepted morning batch pre-generation strategy. |
| [`adr/0007-deepseek-llm-gateway.md`](adr/0007-deepseek-llm-gateway.md) | DeepSeek gateway and task-aware model routing. |
| [`adr/0008-shared-lesson-library.md`](adr/0008-shared-lesson-library.md) | Accepted shared lesson library clone model. |
| [`features/`](features/) | Epic files: original MVP backlog plus learning-engine roadmap and post-MVP extensions. |
| [`features/README.md`](features/README.md) | Epic index, dependency graph, suggested order. |
| [`runbooks/`](runbooks/) | Operational procedures: deploy, demo data, backups, secret handling. |
| [`runbooks/deploy.md`](runbooks/deploy.md) | Deploy checklist and Telegram smoke message format. |
| [`runbooks/curriculum-seed.md`](runbooks/curriculum-seed.md) | Populate the deterministic 20-lesson B2/B2+ curriculum seed. |
| [`runbooks/telegram-workspace.md`](runbooks/telegram-workspace.md) | Refresh pinned help, command menu, and safe Telegram cleanup. |
| [`runbooks/secrets-management.md`](runbooks/secrets-management.md) | Public-git secret and confidential-data handling. |
| [`testing.md`](testing.md) | Standard verification gate and test coverage map. |

## How to read these docs

- The [`PRD.md`](../PRD.md) at the repo root is the *what*: product
  requirements, user scenarios, acceptance criteria.
- [`architecture.md`](architecture.md) + ADRs are the *how*: which
  framework, which DB, which AI model, which deployment pattern.
- [`features/`](features/) bridges the two: each epic file maps a chunk of
  the PRD onto a concrete unit of work with its own acceptance criteria
  and verification plan.
- [`user-guide.md`](user-guide.md) is the learner-facing "how to use the bot"
  guide and the best place to understand the training methodology.
