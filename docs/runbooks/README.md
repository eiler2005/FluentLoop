# Runbooks

Operational procedures for running FluentLoop on a VPS. Empty until
deployment lands.

Planned entries (post-MVP foundation):

- `deploy.md` — first-time deploy of the container to a fresh VPS.
- `restart.md` — restart the bot, view logs, common failure modes.
- `restore.md` — restore the SQLite DB from `data/backups/` after data loss.
- `rotate-secrets.md` — rotate `TELEGRAM_BOT_TOKEN` or AI API key without
  downtime.
- `backup-offsite.md` — copy `data/backups/` off-VPS (P1 enhancement).
