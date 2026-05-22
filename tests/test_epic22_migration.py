from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from fluentloop.db.session import make_engine

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0001_epic22"


def test_epic22_migration_roundtrip_on_copied_sqlite_db(tmp_path) -> None:
    db_path = tmp_path / "fluentloop-copy.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    engine.dispose()
    config = _alembic_config(db_path)

    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" in schema["learning_items_columns"]
    assert "format" in schema["lesson_plans_columns"]
    assert "ix_lesson_plans_format" in schema["lesson_plans_indexes"]
    assert schema["revision"] == REVISION

    command.downgrade(config, "base")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" not in schema["learning_items_columns"]
    assert "format" not in schema["lesson_plans_columns"]
    assert "ix_lesson_plans_format" not in schema["lesson_plans_indexes"]

    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" in schema["learning_items_columns"]
    assert "format" in schema["lesson_plans_columns"]
    assert "ix_lesson_plans_format" in schema["lesson_plans_indexes"]
    assert schema["revision"] == REVISION


def _alembic_config(db_path: Path) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _schema_snapshot(db_path: Path) -> dict[str, object]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        with engine.connect() as connection:
            revision = None
            if inspector.has_table("alembic_version"):
                revision = connection.execute(
                    text("select version_num from alembic_version")
                ).scalar_one_or_none()
        return {
            "learning_items_columns": {
                column["name"] for column in inspector.get_columns("learning_items")
            },
            "lesson_plans_columns": {
                column["name"] for column in inspector.get_columns("lesson_plans")
            },
            "lesson_plans_indexes": {
                index["name"] for index in inspector.get_indexes("lesson_plans")
            },
            "revision": revision,
        }
    finally:
        engine.dispose()
