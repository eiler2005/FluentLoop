from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fluentloop.bot.handlers import handle_channel_help
from fluentloop.config import Settings, get_settings, load_env
from fluentloop.telegram_bot_api import (
    delete_bot_api_message,
    pin_bot_api_message,
    send_bot_api_reply,
    set_bot_commands,
    unpin_all_forum_topic_messages,
)

OLD_BOT_MESSAGE_MARKERS = (
    "#help\nHow FluentLoop works",
    "#help\nFluentLoop English Forum",
    "FluentLoop deploy smoke:",
    "FluentLoop forum deploy smoke:",
    "FluentLoop demo lessons",
    "[CODEX_TEST] FluentLoop",
    "[CODEX_TEST] Material upload",
)
HELP_LEDGER_PATH = Path("data/telegram_help_messages.json")


def load_runtime_env() -> None:
    load_env(Path("secrets/fluentloop.env"))
    load_env(Path(".env"))


def is_outdated_bot_message(text: str) -> bool:
    return any(marker in text for marker in OLD_BOT_MESSAGE_MARKERS)


def load_help_message_ids(path: Path = HELP_LEDGER_PATH) -> list[int]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [int(value) for value in data.get("message_ids", [])]


def save_help_message_ids(
    message_ids: list[int], path: Path = HELP_LEDGER_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"message_ids": sorted(set(message_ids))}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


async def cleanup_old_help_messages(
    settings: Settings, *, limit: int, dry_run: bool
) -> int:
    if not settings.telegram_forum_group_id or not settings.telegram_topic_help_id:
        print("SKIP: help topic is not configured")
        return 0
    message_ids = load_help_message_ids()[:limit]
    if dry_run:
        print(f"DRY: would delete {len(message_ids)} recorded Help message(s)")
        return 0
    if not message_ids:
        print("OK: no recorded Help messages to delete")
        return 0

    deleted = 0
    failed: list[int] = []
    for message_id in message_ids:
        try:
            delete_bot_api_message(
                settings.telegram_bot_token,
                settings.telegram_forum_group_id,
                message_id,
            )
            deleted += 1
        except Exception as exc:  # noqa: BLE001 - deletion limits vary by chat.
            failed.append(message_id)
            print(
                "WARN: recorded Help message cleanup failed: "
                f"{type(exc).__name__}"
            )
    save_help_message_ids(failed)
    return deleted


async def refresh_help_topic(
    settings: Settings, *, cleanup_limit: int, skip_cleanup: bool, dry_run: bool
) -> None:
    if not settings.telegram_forum_group_id or not settings.telegram_topic_help_id:
        print("SKIP: help topic is not configured")
        return

    if dry_run:
        print("DRY: would unpin old Help-topic pins")
    else:
        try:
            unpin_all_forum_topic_messages(
                settings.telegram_bot_token,
                settings.telegram_forum_group_id,
                settings.telegram_topic_help_id,
            )
            print("OK: unpinned Help-topic messages")
        except Exception as exc:  # noqa: BLE001 - posting fresh help is still useful.
            print(f"WARN: could not unpin Help-topic messages: {type(exc).__name__}")

    if not skip_cleanup:
        deleted = await cleanup_old_help_messages(
            settings,
            limit=cleanup_limit,
            dry_run=dry_run,
        )
        action = "would delete" if dry_run else "deleted"
        print(f"OK: {action} {deleted} old bot-authored help/smoke message(s)")

    reply = handle_channel_help(
        str(settings.telegram_forum_group_id),
        message_thread_id=settings.telegram_topic_help_id,
    )
    if dry_run:
        print("DRY: would post and pin fresh Help-topic guide")
        return

    sent = await send_bot_api_reply(settings.telegram_bot_token, reply)
    await pin_bot_api_message(
        settings.telegram_bot_token,
        settings.telegram_forum_group_id,
        sent.message_id,
    )
    previous = load_help_message_ids()
    save_help_message_ids([*previous, sent.message_id])
    print(f"OK: posted and pinned fresh Help-topic guide #{sent.message_id}")


async def run(args: argparse.Namespace) -> int:
    load_runtime_env()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    if args.dry_run:
        print("DRY: no Telegram writes will be made")

    if not args.skip_command_menu:
        if args.dry_run:
            print("DRY: would sync Telegram command menu")
        else:
            set_bot_commands(settings.telegram_bot_token)
            print("OK: synced Telegram command menu")

    if not args.skip_help_refresh:
        await refresh_help_topic(
            settings,
            cleanup_limit=args.cleanup_limit,
            skip_cleanup=args.skip_cleanup,
            dry_run=args.dry_run,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-command-menu", action="store_true")
    parser.add_argument("--skip-help-refresh", action="store_true")
    parser.add_argument("--skip-cleanup", action="store_true")
    parser.add_argument("--cleanup-limit", type=int, default=80)
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
