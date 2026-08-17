# ADR-0005 — Forum workspace routing

**Status:** Accepted
**Date:** 2026-05-07
**Deciders:** Denis Ermilov

## Context

FluentLoop started with a private Telegram channel, `FluentLoop English`, where
the bot posted practice prompts and status messages with logical hashtag
sections such as `#practice_flow` and `#materials_upload`.

The user then created `FluentLoop English Forum`, a Telegram supergroup with
forum topics, and made the bot an admin. The user expects most study work to
happen inside that forum, while the original channel remains useful as a
visible announcement/digest feed.

Telethon remains the main runtime client per ADR-0002, but Telegram forum topic
routing is exposed directly by the Bot API as `message_thread_id`.

## Decision

Use a hybrid Telegram transport:

- Keep Telethon bot mode for receiving commands, free-text messages, callbacks,
  scheduler reminders, and non-topic sends.
- Use the Telegram Bot API for outbound messages that must target a forum topic
  via `message_thread_id`.
- Configure topic ids through ignored env vars:
  `TELEGRAM_FORUM_GROUP_ID`, `TELEGRAM_TOPIC_HELP_ID`,
  `TELEGRAM_TOPIC_PRACTICE_FLOW_ID`, `TELEGRAM_TOPIC_MATERIALS_UPLOAD_ID`,
  `TELEGRAM_TOPIC_FEEDBACK_ID`, `TELEGRAM_TOPIC_NEXT_PROMPT_ID`,
  `TELEGRAM_TOPIC_SUMMARY_ID`, `TELEGRAM_TOPIC_MISTAKES_ID`, and
  `TELEGRAM_TOPIC_STATS_ID`.
- Preserve `TELEGRAM_CHANNEL_ID` as the announcement/digest fallback when the
  forum workspace is not configured.

### Amendment, 2026-08-17 (EPIC-25): answer where you were asked

Routing was applied unconditionally: any practice reply went to the Practice
Flow topic whenever a forum was configured, regardless of where the request
came from. A learner tapping a button in the private chat therefore saw
nothing at all, which is indistinguishable from the bot being broken.

`bot/app._here_or_workspace(event, settings, topic)` now resolves the target
from the originating chat: workspace topics for requests that arrive in the
workspace, the originating chat otherwise. This covers `/today`, `/review`,
`/skip`, the persistent-keyboard taps, and the feedback and summary replies.

Messages that are *addressed to* the workspace rather than answering someone -
the pinned help hub and the channel hubs posted on `/start` - still use
`workspace_destination` directly. The distinction is whether the message is a
reply or a broadcast.

## Consequences

- The primary study UX can live in real Telegram topics: Practice Flow,
  Materials Upload, Feedback, Next Prompts, Summaries, Mistakes, Stats, and
  Help.
- Free-text answers can be entered in the forum group when practice is active;
  the bot still supports private DM fallback.
- The runtime now needs a tiny Bot API helper in addition to Telethon, but no
  extra long-running process or webhook.
- `scripts/setup_telegram_workspace.py` owns one-time operational setup:
  discovering the forum group, creating topics, writing ignored env values,
  generating avatars, setting photos, and pinning help.

