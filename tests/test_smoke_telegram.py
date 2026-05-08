from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_smoke_module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "smoke_telegram.py"
    spec = importlib.util.spec_from_file_location("smoke_telegram", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_format_smoke_message_keeps_plain_text_without_plan() -> None:
    smoke = _load_smoke_module()

    assert smoke.format_smoke_message("Deploy smoke passed.", plans=[]) == (
        "Deploy smoke passed."
    )


def test_format_smoke_message_includes_build_time_and_plan(monkeypatch) -> None:
    smoke = _load_smoke_module()
    monkeypatch.setattr(smoke, "current_time_label", lambda: "2026-05-08 23:05:00 MSK")

    message = smoke.format_smoke_message(
        "[CODEX_TEST] Upload hotfix deployed.",
        plans=[
            "Route upload replies back to Materials Upload.",
            "Accept UTF-8 .md/.txt attachments.",
        ],
        build_id="123 (abc1234)",
    )

    assert "Build: 123 (abc1234)" in message
    assert "Time: 2026-05-08 23:05:00 MSK" in message
    assert "- Route upload replies back to Materials Upload." in message
    assert "- Accept UTF-8 .md/.txt attachments." in message

