from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from fluentloop.db.session import make_engine

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0004_epic25"


def test_epic25_migration_is_idempotent_and_reversible(tmp_path) -> None:
    db_path = tmp_path / "fluentloop-epic25.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    engine.dispose()
    config = _alembic_config(db_path)

    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    _assert_present(schema)
    assert schema["revision"] == REVISION

    # Re-running the head revision must not fail on already-present objects.
    command.stamp(config, "0003_epic24")
    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    _assert_present(schema)

    command.downgrade(config, "0003_epic24")
    schema = _schema_snapshot(db_path)
    assert "vocab_deliveries" not in schema["tables"]
    assert "preferences_json" not in schema["users_columns"]
    assert "priority" not in schema["learning_items_columns"]

    command.upgrade(config, "head")
    _assert_present(_schema_snapshot(db_path))


def _assert_present(schema: dict[str, object]) -> None:
    assert "preferences_json" in schema["users_columns"]
    assert "priority" in schema["learning_items_columns"]
    assert "ix_learning_items_priority" in schema["learning_items_indexes"]
    assert "vocab_deliveries" in schema["tables"]
    assert {
        "user_id",
        "local_date",
        "slot",
        "seq",
        "status",
        "poll_id",
        "message_id",
        "learning_item_ids",
        "payload_json",
    } <= schema["vocab_deliveries_columns"]
    assert {
        "ix_vocab_deliveries_user_id",
        "ix_vocab_deliveries_local_date",
        "ix_vocab_deliveries_slot",
        "ix_vocab_deliveries_poll_id",
    } <= schema["vocab_deliveries_indexes"]


def _alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _schema_snapshot(db_path: Path) -> dict[str, object]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        revision = None
        with engine.connect() as conn:
            if inspector.has_table("alembic_version"):
                revision = conn.execute(
                    text("select version_num from alembic_version")
                ).scalar_one_or_none()
        return {
            "tables": set(inspector.get_table_names()),
            "users_columns": {
                column["name"] for column in inspector.get_columns("users")
            },
            "learning_items_columns": {
                column["name"] for column in inspector.get_columns("learning_items")
            },
            "learning_items_indexes": {
                index["name"] for index in inspector.get_indexes("learning_items")
            },
            "vocab_deliveries_columns": (
                {column["name"] for column in inspector.get_columns("vocab_deliveries")}
                if inspector.has_table("vocab_deliveries")
                else set()
            ),
            "vocab_deliveries_indexes": (
                {index["name"] for index in inspector.get_indexes("vocab_deliveries")}
                if inspector.has_table("vocab_deliveries")
                else set()
            ),
            "revision": revision,
        }
    finally:
        engine.dispose()
