# Simple learning pilot

The owner pilot uses the manual stream from [EPIC-26](../features/EPIC-26-simple-learning-stream.md)
and [ADR-0013](../adr/0013-simple-learning-stream.md). Other profiles default to
advanced mode. Existing personal learning items and progress are retained.

## Release gate

1. Run the [standard verification gate](../testing.md), including the four
   EPIC-26 test modules and SQLite backup tests.
2. Stage only reviewed source, tests, and documentation. Exclude local backups,
   `.env`, `secrets/`, and `AGENTS.md.bak`.
3. Gate the commit: `uv run python scripts/secret_scan.py && git commit ...`.
4. Push the commit and wait for the CI run for that exact SHA to pass.
5. Deploy a clean archive of that SHA with the existing private runtime env.
   `scripts/deploy.sh` creates a verified SQLite backup with the online backup
   API before migrations; this includes committed WAL writes. Keep the previous
   image available for rollback. If it is already absent, retain the previous
   verified commit so its image can be rebuilt. No EPIC-26 schema migration
   is required.

## Import and activation

Validate the reviewed pack locally; the default performs no database writes:

```bash
uv run python scripts/import_lang_lessons.py
```

Expect 19 topics and 86 records. The source hash and content breakdown are in
[the bank catalog](../lesson-catalog/lang-lessons.md). The reviewed overlays
remove ambiguity while retaining every original record.

Inside the deployed project, with the existing owner admission setting:

```bash
docker compose exec -T fluentloop python scripts/import_lang_lessons.py
docker compose exec -T fluentloop python scripts/import_lang_lessons.py \
  --apply --subscribe-pilot --enable-simple
```

If the bot is stopped, use `docker compose run --rm fluentloop python ...`
before starting it. `--apply` explicitly publishes the reviewed owner-curated
pack. It creates 19 templates and 86 template items, then personal copies for
the configured owner. Repeating the command reuses existing rows and preserves
progress. No Telegram messages are sent by the importer. It sets only that
profile's learning mode; vocabulary preferences stay stored.
Matching personal cards gain question/provenance metadata while retaining
curated fields, status, level, and review state. A conflicting existing question
aborts the import transaction; resolve the conflict before retrying.

## Verification

Check container health and sanitized startup logs. Confirm the owner has simple
mode and 86 personal pack items; all other profiles retain their prior mode.
Repeat the import and confirm it creates no additional templates or clones.

In the owner's private chat or original forum topic:

1. `/start` installs Учиться / Прогресс / Ещё. `/study` and bare `/today` show
   one English question, full A/B/C choice text in the message, compact A/B/C
   buttons, Не знаю, and Хватит. Long option labels must never be placed on
   Telegram buttons.
2. Answer one choice. The old question becomes short feedback with a Russian
   explanation and Подробнее; the next question appears in the same chat/topic.
3. An old button cannot create another answer. Не знаю reveals the answer and
   advances once.
4. Interrupt an unanswered question and run `/study` again: it resumes. A
   container restart also resumes that persisted question.
5. Хватит or `/stop` completes the run and shows its result and accuracy. For
   roadmap questions it also shows the general/work split, up to three affected
   modules with their next action, and Прогресс / План buttons. Confirm it never
   calls that a CEFR result. The next launch reselects. Optional writing accepts
   one sentence; skip leaves SRS unchanged.
6. `/progress` distinguishes recognition and writing. Ещё exposes cards,
   review, full lessons, library, upload, and settings. `/today 5` still shows cards.
7. With no eligible normal questions, the summary offers Повторить знакомое.
   Early correct familiar practice does not advance SRS.

Database/handler smoke in a rollback transaction may verify steps without
changing the owner's learning record. Automated tests cover scheduler isolation;
simple profiles receive no learning pushes, pre-generation, or weekly summary.

## Rollback

Use `/settings` to switch the owner to advanced mode, or set only
`learning.mode` to `advanced` with `set_learning_mode` in a database transaction.
This preserves items, attempts, and vocabulary settings. If necessary, start the
previous image with the same data mount. Do not restore an older DB over new
answers merely to undo this mode: the change adds no schema migration.
