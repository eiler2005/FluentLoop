# Runbooks

Operational procedures for running FluentLoop on a VPS.

Available:

- [`deploy.md`](deploy.md) — deploy checklist and Telegram smoke message
  format with build/time/plan notes.
- [`demo-data.md`](demo-data.md) — idempotent demo dataset for audit and smoke
  testing.
- [`curriculum-seed.md`](curriculum-seed.md) — deterministic 20-lesson B2/B2+
  business/IT curriculum seed and EPIC-23 shared-library publish step.
- [`telegram-workspace.md`](telegram-workspace.md) — refresh Telegram command
  menu, pinned Help guide, and safe bot-authored cleanup.
- [`secrets-management.md`](secrets-management.md) — local/VPS secret catalog
  rules and pre-commit scanning.

Planned entries:

- `restart.md` — restart the bot, view logs, common failure modes.
- `restore.md` — restore the SQLite DB from `data/backups/` after data loss.
- `rotate-secrets.md` — rotate `TELEGRAM_BOT_TOKEN` or AI API key without
  downtime.
- `backup-offsite.md` — copy `data/backups/` off-VPS (P1 enhancement).
