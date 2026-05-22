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
uv run --extra dev ruff check src tests scripts
uv run python -m fluentloop --check
uv run python scripts/secret_scan.py
uv run alembic upgrade head
git diff --check
```

For schema changes, verify the live/copy schema before deploy:

```bash
uv run alembic current
uv run python - <<'PY'
from sqlalchemy import create_engine, inspect
from fluentloop.config import get_settings

settings = get_settings()
inspector = inspect(create_engine(settings.db_url))
learning_columns = [c["name"] for c in inspector.get_columns("learning_items")]
lesson_columns = [c["name"] for c in inspector.get_columns("lesson_plans")]
source_columns = [c["name"] for c in inspector.get_columns("source_materials")]
lesson_indexes = [idx["name"] for idx in inspector.get_indexes("lesson_plans")]
tables = set(inspector.get_table_names())
print("learning_items.metadata_json:", "metadata_json" in learning_columns)
print("learning_items.is_template:", "is_template" in learning_columns)
print("lesson_plans.format:", "format" in lesson_columns)
print("lesson_plans.is_template:", "is_template" in lesson_columns)
print("source_materials.is_template:", "is_template" in source_columns)
print("ix_lesson_plans_format:", "ix_lesson_plans_format" in lesson_indexes)
print("evaluation_runs:", "evaluation_runs" in tables)
print("learning_metric_snapshots:", "learning_metric_snapshots" in tables)
PY
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
mounted in `data/`, Telegram bot, scheduler, and local file storage. The deploy
script now creates a pre-migration SQLite backup when the DB exists, builds the
image, runs `alembic upgrade head`, and only then starts the bot container.

## EPIC-23 Seed Library Publish

After a deploy that includes shared-library schema or seed changes, publish the
deterministic B2/B2+ catalog inside the running container:

```bash
docker compose exec -T fluentloop python scripts/publish_seed_library.py
docker compose exec -T fluentloop python scripts/publish_seed_library.py --apply
```

The first command is a dry run. The apply command should report 20 template
lesson plans, 20 template source materials, and 80 template learning items on a
fresh catalog.

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
10. Run `/library`, `/library risk`, `/subscribe <template_id>`, `/lessons`,
    and `/lesson <clone_id>`; confirm practice starts from the cloned lesson,
    not a template row.
11. Run `/help` and `/howto`; confirm the Help topic has one fresh pinned guide.
12. Check logs for provider, callback, and database errors.
13. For EPIC-22 changes, confirm layered feedback buttons and confidence
    rating during a `/today` or `/practice diplomatic` answer.
14. Run `/reflect <short note>` and `/mentor`; confirm reflection/journal
    replies do not error.
15. Smoke operational commands: `/scene 2`, `/brief roadmap review`,
    `/article <short text>`, `/debate remote work`, `/translate_lab planning`,
    and `/fluency432 incident update`.
16. Smoke `/practice sprint` and one lesson-format mode such as
    `/practice notebook` or `/practice genre`.
17. For EPIC-24 changes, run `/baseline`, submit a short
    `/baseline <answer>`, then run `/outcomes` and `/outcomes full`; confirm
    the report shows sample sizes instead of fake progress when data is thin.
18. Confirm `/mentor` includes the latest outcome summary after `/outcomes`.
```
