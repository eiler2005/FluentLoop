# Testing FluentLoop

This page explains the checks used before deploy, commit, and push.

## Standard gate

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests scripts
uv run python -m fluentloop --check
uv run python scripts/secret_scan.py
git diff --check
```

## What the tests cover

- Simple stream: pending-question recovery, atomic duplicate/stale/foreign
  answer rejection, stop/restart, category mixing, cooldowns, small banks,
  explicit familiar practice, and optional writing.
- Broad roadmap: strict catalogue references, portable-plan types and limits,
  general/work retention, user isolation, safe import/export, command routing,
  HTML escaping, generated-view freshness and unchanged assessed progress.
- Roadmap Study: all 48 modules and 144 stages/questions, actual 60/40 and 90/10
  selection, focus/order/pauses, pending recovery, language interleaving, cooldowns,
  genuine independent spaced writing, reused/copy rejection, retained C1 gate,
  self-report separation, personal quarantine and owner/duplicate callback checks.
- Answer feedback: canonical verdicts and legacy aliases, rejected unknown
  statuses, provider-controlled provenance, and writing prompts that preserve
  the supplied level, general/workplace context and task requirements.
- Reviewed pack: schema/content validation, all 86 records, provenance,
  template publication and personal subscription idempotency, and level retention.
- Simple UI and operations: originating chat/topic replies, keyboard dispatch,
  mode changes, scheduler isolation, and recognition/production metric separation.
- Adaptive UI: per-topic `/progress`, personal `/plan`, CEFR wording, Telegram
  message length, advanced-mode compatibility, owner-scoped issue reports,
  hidden transfer keys in generic previews, and unverified writing status.
- Adaptive engine: distinct spaced evidence, 80% readiness, delayed fresh
  transfer, per-topic repair, global ten-topic C1 gate, cross-user isolation,
  genuine model-evaluated independent writing and duplicate callback handling.
- Advanced curriculum: all 270 records and thirty topic stages, content hashes,
  source provenance, preserved legacy pack and idempotent personal subscriptions.
- Question maintenance: blind independent review, invalid/near-duplicate rejection,
  provider failure, per-local-day concurrent claims, item caps, legacy repair,
  issue quarantine, and exclusion of private uploaded content from model payloads.
- Bot foundation and Telegram workspace: command catalog, help text, forum-topic
  routing, command-menu payloads, admission gate, and state storage.
- Material upload: UTF-8 markdown/text intake, extraction fallback, candidate
  approval, LessonPlan creation, and upload-topic replies.
- Learning engine: daily sessions, explicit lesson starts, 15-20 micro-drills,
  practice modes, skip/show-answer flow, SRS updates, and summaries.
- Feedback: compact teacher feedback, stored detailed explanations, disputes,
  weak-item suggestions, and mistake-pattern behavior.
- Curriculum and library: deterministic B2/B2+ seed idempotency, lesson-browser
  commands, shared template publishing, subscription clones, duplicate subscribe
  reuse, and migration roundtrip checks.
- Learning outcomes: monthly baseline runs, held-out retention, productive
  chunk usage, writing/L1 metrics, mistake extinction, Article Lab probe events,
  outcome snapshots, and template-row isolation.
- Operations: smoke message formatting with build/time/plan notes and safe
  Telegram workspace maintenance helpers; verified SQLite backups including WAL.

## Live smoke

For the broad plan, open `/roadmap`, set a track and inspect a general and a
work module. Confirm `/plan` still reports adaptive evidence. Use a rollback
transaction for release smoke edits. Open the downloaded HTML on desktop and
mobile widths: change time/share, search, choose stage, reorder/pause, edit notes,
export/import JSON and reject an invalid file without losing current changes.
`uv run python scripts/workplace_plan.py --check-render docs/curriculum` checks
that the committed views match the source and renderer. The unit suite performs
this check too; live browser verification complements it.

For the integrated Study flow, use [roadmap-study.md](runbooks/roadmap-study.md):
verify the saved plan actually selects a module, answer once, reject the duplicate,
inspect writing and external actions, change the plan while a question is pending,
and verify resume. Run server-side handler smoke in a rolled-back transaction;
never retain artificial learner progress or send unsolicited test messages.

The repeatable browser check uses an isolated headless Chrome profile and no
network calls from the editor. It verifies filtering, stage selection, edits,
pause/resume, persistence, JSON roundtrip, rejected imports, text escaping and
mobile overflow, and saves screenshots in a temporary directory:

```bash
npm install --prefix /tmp/fluentloop-browser playwright
NODE_PATH=/tmp/fluentloop-browser/node_modules node scripts/check_workplace_planner.cjs
```

This optional check requires Chrome; `PLANNER_BROWSER=chromium` selects a
Playwright-installed Chromium instead. It is separate from the Python-only CI.

For the owner simple pilot, follow [simple-learning.md](runbooks/simple-learning.md):
verify `/study`, choices, unknown, stop, resume, per-topic `/progress`,
**Ещё → План**, question issue reporting, and optional writing.
For the adaptive curriculum and bounded maintenance, follow
[adaptive-learning.md](runbooks/adaptive-learning.md). Live profile smoke uses a
rollback transaction; authored model checks use isolated test data and do not
create learner evidence.
For the full mode, run a real Telegram smoke:

1. Run `/help` and `/howto`.
2. Confirm the Help topic has one fresh pinned guide.
3. Run `/library`, `/library risk`, and `/subscribe <template_id>` for one seed
   template.
4. Confirm the subscribed clone appears in `/lessons` and `/lesson <id>`.
5. Run `/topics`, `/lesson random`, and `/today`.
6. Answer at least two prompts.
7. Run `/baseline`, submit one short `/baseline <answer>`, then run
   `/outcomes` and `/outcomes full`.
8. Use `/skip` once and confirm the answer/explanation appears.
9. Check that the smoke message includes build, time, and plan notes.
