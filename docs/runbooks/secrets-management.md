# Secrets Management

FluentLoop keeps implementation logic in git and runtime secrets outside git.
This mirrors the pattern used in `router_configuration`, adapted for Telegram,
AI-provider keys, SQLite learning data, and one VPS deployment.

## What Is Secret

- `TELEGRAM_BOT_TOKEN`.
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
- `TELEGRAM_ALLOWED_USER_ID`, chat ids, forum group ids, and topic ids.
- OpenAI/Anthropic API keys and any future provider credentials.
- Real VPS IP/hostname, SSH username when paired with the host, private SSH key
  paths, and deploy-only ports.
- `.env`, `.env.*`, and everything under `secrets/`.
- `data/`: SQLite DB, sessions, backups, usage logs, lesson notes, answers,
  mistakes, generated Telegram assets, and Bot API discovery caches.
- Local reports, feedback disputes, and private handoff notes.

## Storage Layout

```text
.env                         # local runtime env; gitignored
secrets/fluentloop.env        # canonical private env source; gitignored
data/fluentloop.sqlite        # live learning DB; gitignored
data/backups/                 # SQLite backups; gitignored
data/sessions/                # Telethon session files; gitignored
reports/                      # local generated reports; gitignored
feedback_disputes/            # local feedback dispute JSONL; gitignored
.env.example                  # placeholder template; safe for git
scripts/env_template.txt      # placeholder template; safe for git
```

## First-Time Setup

```bash
cp .env.example .env
chmod 600 .env
```

Fill `.env` locally or copy from the private `secrets/fluentloop.env` catalog.
Never paste real values into `.env.example`, docs, commit messages, or CI logs.

For deploy scripts, pass VPS details through environment variables or `.env`:

```bash
VPS_HOST=<vps-host> VPS_USER=<ssh-user> bash scripts/deploy.sh
```

Or keep deploy-only coordinates in `secrets/deploy.env`:

```bash
VPS_HOST=<vps-host>
VPS_USER=<ssh-user>
VPS_PORT=22
```

## Pre-Push Checklist

```bash
python3 scripts/secret_scan.py
python3 scripts/secret_scan.py --history   # before first public push
uv run --python 3.11 --with ruff ruff check src tests scripts
uv run --python 3.11 --with pytest --with pytest-asyncio pytest -q
git status --short
git diff --check
```

The scanner checks tracked and untracked non-ignored text files for common
FluentLoop leaks: Telegram bot-token shaped values, AI keys, private-key
markers, public VPS IP literals, real-looking secret env assignments, known
sensitive literals, and email addresses.

Before publishing a public remote, also check git history with `--history`. If
old commits contain production literals, do not push the private history as-is.
Either publish a fresh sanitized snapshot or rewrite history with explicit
owner approval.

## Documentation Rules

- Use placeholders: `<vps-host>`, `<ssh-user>`, `<your-telegram-user-id>`,
  `<telegram-channel-id>`, `<openai-api-key>`.
- Use `example.invalid` for hostnames and RFC 5737 example IPs for docs:
  `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`.
- Do not include screenshots that reveal tokens, numeric Telegram ids,
  colleague/client names, private lesson text, or live VPS coordinates.
- Treat `MORNING_REPORT.md`, `NIGHT_RUN.md`, and `NIGHT_QUESTIONS.md` as public
  docs once tracked. Put private operational values in `secrets/` instead.
