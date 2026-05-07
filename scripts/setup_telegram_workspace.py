#!/usr/bin/env python3
"""Configure the FluentLoop Telegram forum workspace.

The script is intentionally safe for git: it reads/writes only ignored runtime
files (.env and data/telegram_assets) and never prints token values or chat IDs.
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from fluentloop.telegram_workspace import TOPIC_ENV_VARS, TOPIC_NAMES

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
ASSET_DIR = REPO_ROOT / "data" / "telegram_assets"

AVATARS = {
    "bot": {
        "filename": "fluentloop-bot.jpg",
        "title": "FL",
        "palette": ((28, 94, 117), (76, 189, 159), (244, 190, 92)),
    },
    "channel": {
        "filename": "fluentloop-channel.jpg",
        "title": "FE",
        "palette": ((42, 130, 87), (113, 214, 109), (247, 201, 96)),
    },
    "forum": {
        "filename": "fluentloop-forum.jpg",
        "title": "FF",
        "palette": ((232, 143, 63), (255, 203, 111), (45, 136, 168)),
    },
}


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
        os.environ.setdefault(key.strip(), value.strip())
    return values


def update_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.partition("=")[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    missing = [key for key in updates if key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.extend(f"{key}={updates[key]}" for key in missing)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    path.chmod(0o600)


def call_json(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"{method} HTTP {exc.code}: {body}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == 2:
                raise RuntimeError(f"{method} network error: {exc}") from exc
            time.sleep(1 + attempt)
    if not parsed.get("ok"):
        raise RuntimeError(f"{method} failed: {parsed.get('description', parsed)}")
    return parsed


def call_multipart(
    token: str,
    method: str,
    fields: dict[str, str],
    files: dict[str, Path],
) -> dict[str, Any]:
    boundary = "----fluentloop-" + secrets.token_hex(12)
    body = bytearray()
    for key, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")
    for key, path in files.items():
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{key}"; '
                f'filename="{path.name}"\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"{method} HTTP {exc.code}: {body_text}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == 2:
                raise RuntimeError(f"{method} network error: {exc}") from exc
            time.sleep(1 + attempt)
    if not parsed.get("ok"):
        raise RuntimeError(f"{method} failed: {parsed.get('description', parsed)}")
    return parsed


def discover_chat_id(token: str, title: str) -> str | None:
    payload = {"limit": 100, "allowed_updates": ["message", "my_chat_member"]}
    updates = call_json(token, "getUpdates", payload).get("result", [])
    for update in updates:
        for key in ("message", "edited_message", "my_chat_member"):
            obj = update.get(key) or {}
            chat = obj.get("chat") or {}
            if chat.get("title") == title:
                return str(chat["id"])
    return None


def ensure_forum_topics(
    token: str, chat_id: str, env_values: dict[str, str]
) -> dict[str, str]:
    updates: dict[str, str] = {}
    colors = [7322096, 16766590, 13338331, 9367192, 16749490, 16478047]
    for index, (key, name) in enumerate(TOPIC_NAMES.items()):
        env_var = TOPIC_ENV_VARS[key]
        if env_values.get(env_var):
            continue
        parsed = call_json(
            token,
            "createForumTopic",
            {
                "chat_id": chat_id,
                "name": name,
                "icon_color": colors[index % len(colors)],
            },
        )
        updates[env_var] = str(parsed["result"]["message_thread_id"])
        print(f"OK: created topic {name!r}")
    return updates


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def generate_avatar(
    path: Path, title: str, palette: tuple[tuple[int, int, int], ...]
) -> None:
    size = 512
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    a, b, c = palette
    for y in range(size):
        for x in range(size):
            t = (x + y) / (size * 2)
            wave = (1 + math.sin((x - y) / 54)) / 2
            r = int(a[0] * (1 - t) + b[0] * t + c[0] * 0.12 * wave)
            g = int(a[1] * (1 - t) + b[1] * t + c[1] * 0.12 * wave)
            bl = int(a[2] * (1 - t) + b[2] * t + c[2] * 0.12 * wave)
            pixels[x, y] = (min(r, 255), min(g, 255), min(bl, 255))

    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((82, 82, 430, 430), outline=(255, 255, 255, 76), width=22)
    draw.arc(
        (118, 118, 394, 394),
        start=215,
        end=520,
        fill=(255, 255, 255, 160),
        width=28,
    )
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    font = _font(144)
    bbox = shadow_draw.textbbox((0, 0), title, font=font)
    text_x = (size - (bbox[2] - bbox[0])) / 2
    text_y = (size - (bbox[3] - bbox[1])) / 2 - 10
    shadow_draw.text((text_x + 5, text_y + 7), title, font=font, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    overlay.alpha_composite(shadow)
    draw = ImageDraw.Draw(overlay)
    draw.text((text_x, text_y), title, font=font, fill=(255, 255, 255, 245))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=94, optimize=True)


def generate_avatars() -> dict[str, Path]:
    assets: dict[str, Path] = {}
    for key, spec in AVATARS.items():
        path = ASSET_DIR / str(spec["filename"])
        generate_avatar(path, str(spec["title"]), spec["palette"])
        assets[key] = path
        print(f"OK: generated {key} avatar at {path.relative_to(REPO_ROOT)}")
    return assets


def set_chat_photo(token: str, chat_id: str, path: Path, label: str) -> None:
    call_multipart(token, "setChatPhoto", {"chat_id": chat_id}, {"photo": path})
    print(f"OK: set {label} avatar")


def set_bot_photo(token: str, path: Path) -> None:
    photo = json.dumps({"type": "static", "photo": "attach://photo"})
    call_multipart(token, "setMyProfilePhoto", {"photo": photo}, {"photo": path})
    print("OK: set bot avatar")


def post_and_pin_workspace_help(
    token: str, chat_id: str, env_values: dict[str, str]
) -> None:
    help_thread = env_values.get("TELEGRAM_TOPIC_HELP_ID")
    if not help_thread:
        return
    text = (
        "#help\n"
        "FluentLoop English Forum is the main study space.\n\n"
        "Practice Flow: start and answer daily exercises.\n"
        "Materials Upload: send /upload, then paste lesson notes or feedback.\n"
        "Feedback: answer checks and corrections.\n"
        "Next Prompts: follow-up exercises.\n"
        "Mistakes: recurring weak points.\n"
        "Summaries and Stats: progress snapshots.\n\n"
        "FluentLoop English remains the announcement channel."
    )
    sent = call_json(
        token,
        "sendMessage",
        {"chat_id": chat_id, "message_thread_id": int(help_thread), "text": text},
    )
    call_json(
        token,
        "pinChatMessage",
        {
            "chat_id": chat_id,
            "message_id": sent["result"]["message_id"],
            "disable_notification": True,
        },
    )
    print("OK: posted and pinned forum help")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-photos", action="store_true")
    parser.add_argument("--skip-topics", action="store_true")
    parser.add_argument("--skip-help", action="store_true")
    args = parser.parse_args()

    env_values = load_env()
    token = env_values.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("FAIL: TELEGRAM_BOT_TOKEN must be set", file=sys.stderr)
        return 2

    updates: dict[str, str] = {}
    forum_title = env_values.get("TELEGRAM_FORUM_TITLE", "FluentLoop English Forum")
    forum_group_id = env_values.get("TELEGRAM_FORUM_GROUP_ID", "")
    if not forum_group_id:
        forum_group_id = discover_chat_id(token, forum_title) or ""
        if forum_group_id:
            updates["TELEGRAM_FORUM_GROUP_ID"] = forum_group_id
            print("OK: discovered forum group")
        else:
            print(f"FAIL: could not discover forum group titled {forum_title!r}")
            return 1

    if not args.skip_topics:
        topic_updates = ensure_forum_topics(
            token, forum_group_id, {**env_values, **updates}
        )
        updates.update(topic_updates)

    if updates:
        update_env(ENV_PATH, updates)
        env_values.update(updates)
        print("OK: wrote forum workspace settings to .env")

    if not args.skip_photos:
        assets = generate_avatars()
        channel_id = env_values.get("TELEGRAM_CHANNEL_ID", "")
        if channel_id:
            try:
                set_chat_photo(token, channel_id, assets["channel"], "channel")
            except RuntimeError as exc:
                print(f"WARN: channel avatar not changed: {exc}")
        try:
            set_chat_photo(token, forum_group_id, assets["forum"], "forum")
        except RuntimeError as exc:
            print(f"WARN: forum avatar not changed: {exc}")
        try:
            set_bot_photo(token, assets["bot"])
        except RuntimeError as exc:
            print(f"WARN: bot avatar not changed: {exc}")

    if not args.skip_help:
        post_and_pin_workspace_help(token, forum_group_id, env_values)

    print("OK: Telegram workspace setup complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
