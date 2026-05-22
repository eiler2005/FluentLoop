# B2/B2+ Curriculum Seed

Use this runbook to populate the local SQLite database with the deterministic
20-lesson B2/B2+ business/IT catalog. The seed does not call DeepSeek.
EPIC-23 can also publish the same catalog as shared templates for `/library`.

## What It Creates

- 20 active `LessonPlan` rows.
- 80 linked `LearningItem` rows.
- `SourceMaterial`, `LessonStep`, and `LessonPlanItem` rows for each lesson.
- Tags include `curriculum:b2-b2plus` and the lesson slug.
- In shared-library mode, the templates are owned by an internal seed-library
  user and user subscriptions create private per-user clones.

The review/export source is:

- [`../curriculum/b2_b2plus_lesson_catalog.md`](../curriculum/b2_b2plus_lesson_catalog.md)

## Local Seed

```bash
uv run python scripts/seed_b2_curriculum.py
```

## Shared Library Publish

Dry-run the deterministic seed library publish:

```bash
uv run python scripts/publish_seed_library.py
```

Apply it to the configured DB:

```bash
uv run python scripts/publish_seed_library.py --apply
```

Expected dry-run/apply output includes `templates=20` on a fresh DB. Re-running
is idempotent; existing template rows are reused.

Optional DB override for a dry run:

```bash
uv run python scripts/seed_b2_curriculum.py \
  --db-url sqlite:////tmp/fluentloop-b2-seed.sqlite \
  --write-markdown /tmp/fluentloop-b2-catalog.md
```

Expected output:

```text
OK: B2/B2+ curriculum seeded lessons=20 items=80
```

## Manual Telegram Check

After seeding, use:

```text
/library
/library risk
/subscribe <template_id>
/topics
/lessons risk
/lesson random
/lesson topic risk
/practice grammar
```

`/library` browses shared seed templates. `/subscribe <template_id>` copies one
template into the user's own lesson base. `/lesson random` and
`/lesson topic <query>` start a lesson-mode practice session immediately.
`/lesson <id>` shows lesson details first.
