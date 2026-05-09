# B2/B2+ Curriculum Seed

Use this runbook to populate the local SQLite database with the deterministic
20-lesson B2/B2+ business/IT catalog. The seed does not call DeepSeek.

## What It Creates

- 20 active `LessonPlan` rows.
- 80 linked `LearningItem` rows.
- `SourceMaterial`, `LessonStep`, and `LessonPlanItem` rows for each lesson.
- Tags include `curriculum:b2-b2plus` and the lesson slug.

The review/export source is:

- [`../curriculum/b2_b2plus_lesson_catalog.md`](../curriculum/b2_b2plus_lesson_catalog.md)

## Local Seed

```bash
uv run python scripts/seed_b2_curriculum.py
```

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
/topics
/lessons risk
/lesson random
/lesson topic risk
/practice grammar
```

`/lesson random` and `/lesson topic <query>` start a lesson-mode practice
session immediately. `/lesson <id>` shows lesson details first.
