from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fluentloop.db.models import User


def record_reflection(
    user: User,
    text: str,
    *,
    base_dir: Path = Path("data/reflections"),
    now: datetime | None = None,
) -> Path:
    current = now or datetime.now(UTC)
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{current.date().isoformat()}.jsonl"
    payload = {
        "created_at": current.isoformat(),
        "user_id": user.id,
        "telegram_user_id": user.telegram_user_id,
        "text": text.strip(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def reflection_prompt() -> str:
    return (
        "Reflective practice\n"
        "Use /reflect <text> with one honest note: what was hardest today, "
        "what felt easier, or where you still lacked English at work."
    )
