# Telegram Workspace Maintenance

Use this runbook after changing commands, help text, topic routing, or onboarding
copy.

## Refresh Help And Commands

```bash
uv run python scripts/telegram_workspace_maintenance.py
```

The script:

- syncs Telegram's command menu with the current supported commands;
- unpins old messages in the Help forum topic;
- tries to delete only bot-authored outdated help/smoke messages with known
  markers;
- posts and pins the current Help guide.

If Telegram refuses deletion because the message is too old or permissions are
insufficient, the script leaves history untouched and still pins the fresh help.
It never deletes user uploads, user answers, lesson data, or arbitrary topic
history.

## Dry Run

```bash
uv run python scripts/telegram_workspace_maintenance.py --dry-run
```

Use dry-run before changing cleanup behavior or after moving the bot to a new
forum group.

## Required Secrets

Values are loaded from `secrets/fluentloop.env` first and then from `.env` when
not already present. This keeps local secret catalog values authoritative while
still allowing a copied `.env` on the VPS:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_FORUM_GROUP_ID`
- `TELEGRAM_TOPIC_HELP_ID`

Do not commit real values. Keep local secret files under `secrets/` with mode
`600`.
