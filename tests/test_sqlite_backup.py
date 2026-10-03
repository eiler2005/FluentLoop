from __future__ import annotations

import runpy
import sqlite3
from pathlib import Path

import pytest

backup_sqlite = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "backup_sqlite.py")
)["backup_sqlite"]


def test_backup_includes_committed_wal_and_preserves_existing_backup(tmp_path):
    source = tmp_path / "live.sqlite"
    destination = tmp_path / "backups" / "verified.sqlite"
    with sqlite3.connect(source) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("PRAGMA wal_autocheckpoint=0")
        live.execute("CREATE TABLE entries (value TEXT)")
        live.execute("INSERT INTO entries VALUES ('approved')")
        live.commit()
        assert source.with_name(source.name + "-wal").is_file()
        assert backup_sqlite(source, destination)
        with sqlite3.connect(destination) as restored:
            assert restored.execute("SELECT value FROM entries").fetchall() == [
                ("approved",)
            ]
            assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert destination.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError):
            backup_sqlite(source, destination)


def test_missing_database_is_not_created(tmp_path):
    source = tmp_path / "missing.sqlite"
    destination = tmp_path / "backup.sqlite"
    assert not backup_sqlite(source, destination)
    assert not source.exists()
    assert not destination.exists()
