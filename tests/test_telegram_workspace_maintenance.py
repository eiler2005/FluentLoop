from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_maintenance_module():
    path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "telegram_workspace_maintenance.py"
    )
    spec = importlib.util.spec_from_file_location(
        "telegram_workspace_maintenance", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_outdated_help_cleanup_markers_are_scoped_to_bot_help_and_smoke() -> None:
    maintenance = _load_maintenance_module()

    assert maintenance.is_outdated_bot_message("#help\nHow FluentLoop works")
    assert maintenance.is_outdated_bot_message(
        "[CODEX_TEST] Material upload topic routing hotfix deployed."
    )
    assert not maintenance.is_outdated_bot_message(
        "Real lesson upload: reported speech and workplace opinions"
    )
    assert not maintenance.is_outdated_bot_message("/today answer from the user")


def test_help_message_ledger_round_trips_unique_ids() -> None:
    maintenance = _load_maintenance_module()

    path = Path("/tmp/fluentloop-help-ledger-test.json")
    try:
        maintenance.save_help_message_ids([10, 10, 11], path=path)
        assert maintenance.load_help_message_ids(path=path) == [10, 11]
    finally:
        path.unlink(missing_ok=True)
