# Documentation index

| File | Purpose |
|---|---|
| [`architecture.md`](architecture.md) | Tech architecture: framework, libraries, DB, scheduler, AI providers, deployment, learning-engine runtime notes. |
| [`user-guide.md`](user-guide.md) | Bilingual learner guide: simple stream, per-topic `/progress`, personal `/plan`, practice modes, and outcomes. |
| [`learning-methodology.md`](learning-methodology.md) | Learner-facing method: input -> lesson type -> practice mode -> exercise -> feedback -> SRS/mistakes -> outcomes. |
| [`learning-plans.md`](learning-plans.md) | Practical first-week, 30-day, and 12-week learner plans using `/baseline`, `/today`, focused practice modes, and `/outcomes`. |
| [`material-upload-guide.md`](material-upload-guide.md) | User-facing cookbook for preparing lesson notes, feedback, articles, transcripts, and LLM-assisted upload material. |
| [`lesson-catalog/`](lesson-catalog/) | Generated public catalog: lesson types, B2/B2+ seed lessons, English for Tech, and 40 business/IT scenarios. |
| [`adr/`](adr/) | Architecture decision records. Each captures one significant choice. |
| [`adr/0001-template.md`](adr/0001-template.md) | Reusable ADR template. |
| [`adr/0002-telegram-library-choice.md`](adr/0002-telegram-library-choice.md) | Accepted Telegram library choice. |
| [`adr/0003-ai-model-tiering-and-cost.md`](adr/0003-ai-model-tiering-and-cost.md) | Accepted two-tier model strategy and cost envelope. |
| [`adr/0004-exercise-pre-generation-strategy.md`](adr/0004-exercise-pre-generation-strategy.md) | Accepted morning batch pre-generation strategy. |
| [`adr/0007-deepseek-llm-gateway.md`](adr/0007-deepseek-llm-gateway.md) | DeepSeek gateway and task-aware model routing. |
| [`adr/0008-shared-lesson-library.md`](adr/0008-shared-lesson-library.md) | Accepted shared lesson library clone model. |
| [`adr/0013-simple-learning-stream.md`](adr/0013-simple-learning-stream.md) | Manual simple stream, persisted answers, cooldowns, and separate recognition metrics. |
| [`adr/0014-adaptive-topic-progression.md`](adr/0014-adaptive-topic-progression.md) | Adaptive stages, fresh transfer, genuine writing, repair and bounded question maintenance. |
| [`curriculum/adaptive-b2-c1.md`](curriculum/adaptive-b2-c1.md) | Ten topic plans from B2 through strong B2 to introductory C1; 270 reviewed questions. |
| [`curriculum/workplace-plan-guide.md`](curriculum/workplace-plan-guide.md) | Start and customise the general-English programme and workplace supplements; Telegram commands, offline editor and personal JSON. |
| [`curriculum/workplace-roadmap.md`](curriculum/workplace-roadmap.md) | Generated 48-module map with 144 stage tasks, evidence criteria and language coverage gaps. |
| [`curriculum/workplace-planner.html`](curriculum/workplace-planner.html) | Downloadable offline visual planner: search/filter, priorities, time split, order, pauses and notes. |
| [`research/README.md`](research/README.md) | Primary-source CEFR and general/workplace needs research. |
| [`adr/0015-editable-workplace-roadmap.md`](adr/0015-editable-workplace-roadmap.md) | Advisory personal plans stay separate from assessed progress. |
| [`features/`](features/) | Epic files: original MVP backlog plus learning-engine roadmap and post-MVP extensions. |
| [`features/README.md`](features/README.md) | Epic index, dependency graph, suggested order. |
| [`runbooks/`](runbooks/) | Operational procedures: deploy, demo data, backups, secret handling. |
| [`runbooks/deploy.md`](runbooks/deploy.md) | Deploy checklist and Telegram smoke message format. |
| [`runbooks/simple-learning.md`](runbooks/simple-learning.md) | Reviewed bank import, owner pilot activation, checks, and rollback. |
| [`runbooks/adaptive-learning.md`](runbooks/adaptive-learning.md) | Adaptive curriculum activation, maintenance limits, owner opt-out, smoke and rollback. |
| [`lesson-catalog/lang-lessons.md`](lesson-catalog/lang-lessons.md) | Reviewed 86-question phrase/grammar bank and source provenance. |
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
  guide. [`learning-methodology.md`](learning-methodology.md) is the clean
  method map. [`lesson-catalog/`](lesson-catalog/) is generated from DB/code
  and shows the current public lessons and lesson types.
