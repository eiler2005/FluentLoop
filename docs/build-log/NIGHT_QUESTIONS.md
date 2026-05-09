# NIGHT_QUESTIONS

## 1. Channel discovery did not expose `FluentLoop English`

**Epic:** EPIC-08-daily-practice-telegram.md  
**Where:** `scripts/discover_channel.py` / design-level  
**What's blocked:** Bot API `getUpdates` had no recent channel updates for
`FluentLoop English`, and Telethon bot-mode cannot call `GetDialogsRequest`.
Without a channel id or a fresh channel event visible to the bot, the app
cannot reliably post full practice to the channel.  
**Default I would use if forced:** Keep channel support configurable via
`TELEGRAM_CHANNEL_ID` and fall back to the allowed user's private chat.  
**Why I'd prefer to ask:** A private channel id is sensitive enough that it
should not be guessed or committed.

**Resolved 2026-05-07:** After the bot was added as channel admin, Bot API
updates exposed `FluentLoop English`. `TELEGRAM_CHANNEL_ID` was written only to
ignored local/VPS env files, channel send/delete smoke passed, and channel-mode
practice routing is deployed.

## 2. Docker daemon unavailable locally

**Epic:** EPIC-01-bot-foundation.md  
**Where:** `docker compose build`  
**What's blocked:** Local Docker daemon was not reachable from this shell:
`Cannot connect to the Docker daemon`.  
**Default I would use if forced:** Use `uv --python 3.11` for local green gates
and let `scripts/deploy.sh`/VPS Docker perform the container build when SSH is
reachable.  
**Why I'd prefer to ask:** Docker Desktop may simply need to be started on the
Mac before local container verification.

**Resolved during night:** VPS Docker build succeeded via `scripts/deploy.sh`.
Local Docker Desktop may still be stopped, but deployment no longer depends on
local Docker.

## 3. VPS SSH became unreachable after initial success

**Epic:** deployment after Telegram-visible epics  
**Where:** `scripts/check_vps.sh`  
**What's blocked:** The VPS check passed earlier, then repeated attempts timed
out during SSH banner exchange. Deploy and post-deploy smoke tests were skipped.  
**Default I would use if forced:** Do not deploy; keep the local repo green and
retry `scripts/check_vps.sh` before the next deployment attempt.  
**Why I'd prefer to ask:** A timed-out SSH banner can indicate VPS load,
network filtering, or transient host issues; forced retries risk wasting the
night without changing code.

**Resolved during night:** VPS SSH recovered. Deployment now succeeds to
`/opt/fluentloop-bot` after `scripts/deploy.sh` creates/chowns the service
directory with sudo when needed.
