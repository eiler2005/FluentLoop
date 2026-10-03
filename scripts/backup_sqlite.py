"""Create and verify a consistent SQLite backup, including pending WAL writes."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_sqlite(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    if destination.exists():
        raise FileExistsError("Backup destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.touch(mode=0o600, exist_ok=False)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True)) as live,
        closing(sqlite3.connect(destination)) as backup,
    ):
        live.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("SQLite backup failed integrity verification")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    created = backup_sqlite(args.source, args.destination)
    print("SQLite backup verified" if created else "No existing SQLite database")


if __name__ == "__main__":
    main()
