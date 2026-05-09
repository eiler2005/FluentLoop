# Testing FluentLoop

This page explains the checks used before deploy, commit, and push.

## Standard gate

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
uv run python -m fluentloop --check
uv run python scripts/secret_scan.py
git diff --check
```

## What the tests cover

- Bot foundation and Telegram workspace: command catalog, help text, forum-topic
  routing, command-menu payloads, single-user gate, and state storage.
- Material upload: UTF-8 markdown/text intake, extraction fallback, candidate
  approval, LessonPlan creation, and upload-topic replies.
- Learning engine: daily sessions, explicit lesson starts, 15-20 micro-drills,
  practice modes, skip/show-answer flow, SRS updates, and summaries.
- Feedback: compact teacher feedback, stored detailed explanations, disputes,
  weak-item suggestions, and mistake-pattern behavior.
- Curriculum: deterministic B2/B2+ seed idempotency and lesson-browser commands.
- Operations: smoke message formatting with build/time/plan notes and safe
  Telegram workspace maintenance helpers.

## Live smoke

After deploy, run a real Telegram smoke:

1. Run `/help` and `/howto`.
2. Confirm the Help topic has one fresh pinned guide.
3. Run `/topics`, `/lessons`, `/lesson random`, and `/today`.
4. Answer at least two prompts.
5. Use `/skip` once and confirm the answer/explanation appears.
6. Check that the smoke message includes build, time, and plan notes.
