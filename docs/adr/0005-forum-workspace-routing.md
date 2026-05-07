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

