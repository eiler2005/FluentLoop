# Deploy and Smoke

Operational checklist for deploying FluentLoop to the VPS and leaving a useful
Telegram smoke trail.

## Preconditions

- Deploy coordinates are provided through environment variables or
  `secrets/deploy.env`.
- Runtime secrets live only in `.env`/`secrets/`; never in git.
- Before schema changes on the live SQLite DB, create and verify a backup under
  `data/backups/`.

## Local Verification

```bash
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
uv run python -m fluentloop --check
uv run python scripts/secret_scan.py
git diff --check
```

When Help text or commands changed, verify the Telegram maintenance path before
deploying:

```bash
uv run python scripts/telegram_workspace_maintenance.py --dry-run
```

## Deploy

```bash
bash scripts/deploy.sh
```

The deployment keeps the same lightweight shape: one Docker container, SQLite
mounted in `data/`, Telegram bot, scheduler, and local file storage.

## Telegram Smoke Message

After deploy, send a smoke message that includes what changed, build id, and
local time:

```bash
uv run python scripts/smoke_telegram.py \
  --text "[CODEX_TEST] Material upload topic routing hotfix deployed." \
  --plan "Upload replies stay in the Materials Upload topic." \
  --plan "DeepSeek extraction uses planner -> fast -> deterministic fallback." \
  --plan "Practice header shows lesson title and dynamic Step X/N."
```

`scripts/smoke_telegram.py` automatically appends:

- `Build: <git commit count> (<short sha>)`, unless `--build-id` is supplied.
- `Time: <local timestamp>`.
- Every `--plan` line as a short implementation/validation note.

## Live Smoke Checklist

```text
1. Upload a lesson markdown file in Materials Upload.
2. Confirm extraction reply appears in the same topic.
3. Confirm the reply shows lesson title, knowledge areas, and full candidates
   when Telegram limits allow it.
4. Approve all candidates.
5. Run /today.
6. Confirm the header shows Lesson, Mode, Topic, Goal, Focus, and Why now.
7. Confirm the session uses dynamic Step X/N with about 15-20 micro-drills.
8. Answer at least two drills and confirm PracticeAttempt + SRS update.
9. Use /skip once and confirm the correct answer/explanation is shown.
10. Run `/help` and `/howto`; confirm the Help topic has one fresh pinned guide.
11. Check logs for provider, callback, and database errors.
```
