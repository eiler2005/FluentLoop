from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from fluentloop.db.session import make_engine

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0004_epic25"


def test_epic22_migration_roundtrip_on_copied_sqlite_db(tmp_path) -> None:
    db_path = tmp_path / "fluentloop-copy.sqlite"
    engine = make_engine(f"sqlite:///{db_path}")
    engine.dispose()
    config = _alembic_config(db_path)

    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" in schema["learning_items_columns"]
    assert "is_template" in schema["learning_items_columns"]
    assert "template_of" in schema["learning_items_columns"]
    assert "format" in schema["lesson_plans_columns"]
    assert "is_template" in schema["lesson_plans_columns"]
    assert "template_of" in schema["lesson_plans_columns"]
    assert "is_template" in schema["source_materials_columns"]
    assert "template_of" in schema["source_materials_columns"]
    assert "ix_lesson_plans_format" in schema["lesson_plans_indexes"]
    assert "ix_lesson_plans_is_template" in schema["lesson_plans_indexes"]
    assert "evaluation_runs" in schema["tables"]
    assert "learning_metric_snapshots" in schema["tables"]
    assert {
        "user_id",
        "kind",
        "prompt",
        "answer_text",
        "metrics_json",
        "held_out_item_ids",
        "period_start",
        "period_end",
    } <= schema["evaluation_runs_columns"]
    assert {
        "user_id",
        "period_start",
        "period_end",
        "metrics_json",
        "summary_text",
    } <= schema["learning_metric_snapshots_columns"]
    assert "ix_evaluation_runs_user_id" in schema["evaluation_runs_indexes"]
    assert (
        "ix_learning_metric_snapshots_user_id"
        in schema["learning_metric_snapshots_indexes"]
    )
    assert schema["revision"] == REVISION

    command.downgrade(config, "base")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" not in schema["learning_items_columns"]
    assert "is_template" not in schema["learning_items_columns"]
    assert "template_of" not in schema["learning_items_columns"]
    assert "format" not in schema["lesson_plans_columns"]
    assert "is_template" not in schema["lesson_plans_columns"]
    assert "template_of" not in schema["lesson_plans_columns"]
    assert "is_template" not in schema["source_materials_columns"]
    assert "template_of" not in schema["source_materials_columns"]
    assert "ix_lesson_plans_format" not in schema["lesson_plans_indexes"]
    assert "evaluation_runs" not in schema["tables"]
    assert "learning_metric_snapshots" not in schema["tables"]

    command.upgrade(config, "head")
    schema = _schema_snapshot(db_path)
    assert "metadata_json" in schema["learning_items_columns"]
    assert "is_template" in schema["learning_items_columns"]
    assert "template_of" in schema["learning_items_columns"]
    assert "format" in schema["lesson_plans_columns"]
    assert "is_template" in schema["lesson_plans_columns"]
    assert "template_of" in schema["lesson_plans_columns"]
    assert "is_template" in schema["source_materials_columns"]
    assert "template_of" in schema["source_materials_columns"]
    assert "ix_lesson_plans_format" in schema["lesson_plans_indexes"]
    assert "ix_lesson_plans_is_template" in schema["lesson_plans_indexes"]
    assert "evaluation_runs" in schema["tables"]
    assert "learning_metric_snapshots" in schema["tables"]
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
            "tables": set(inspector.get_table_names()),
            "learning_items_columns": {
                column["name"] for column in inspector.get_columns("learning_items")
            },
            "lesson_plans_columns": {
                column["name"] for column in inspector.get_columns("lesson_plans")
            },
            "source_materials_columns": {
                column["name"] for column in inspector.get_columns("source_materials")
            },
            "lesson_plans_indexes": {
                index["name"] for index in inspector.get_indexes("lesson_plans")
            },
            "evaluation_runs_columns": (
                {column["name"] for column in inspector.get_columns("evaluation_runs")}
                if inspector.has_table("evaluation_runs")
                else set()
            ),
            "evaluation_runs_indexes": (
                {index["name"] for index in inspector.get_indexes("evaluation_runs")}
                if inspector.has_table("evaluation_runs")
                else set()
            ),
            "learning_metric_snapshots_columns": (
                {
                    column["name"]
                    for column in inspector.get_columns("learning_metric_snapshots")
                }
                if inspector.has_table("learning_metric_snapshots")
                else set()
            ),
            "learning_metric_snapshots_indexes": (
                {
                    index["name"]
                    for index in inspector.get_indexes("learning_metric_snapshots")
                }
                if inspector.has_table("learning_metric_snapshots")
                else set()
            ),
            "revision": revision,
        }
    finally:
        engine.dispose()
