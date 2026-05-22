from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_epic22"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    learning_item_columns = _column_names(inspector, "learning_items")
    lesson_plan_columns = _column_names(inspector, "lesson_plans")
    lesson_plan_indexes = _index_names(inspector, "lesson_plans")

    if "metadata_json" not in learning_item_columns:
        op.add_column(
            "learning_items",
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        )
    if "format" not in lesson_plan_columns:
        op.add_column(
            "lesson_plans",
            sa.Column(
                "format",
                sa.String(length=64),
                nullable=False,
                server_default="lesson",
            ),
        )
    if "ix_lesson_plans_format" not in lesson_plan_indexes:
        op.create_index("ix_lesson_plans_format", "lesson_plans", ["format"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    learning_item_columns = _column_names(inspector, "learning_items")
    lesson_plan_columns = _column_names(inspector, "lesson_plans")
    lesson_plan_indexes = _index_names(inspector, "lesson_plans")

    if "ix_lesson_plans_format" in lesson_plan_indexes:
        op.drop_index("ix_lesson_plans_format", table_name="lesson_plans")
    if "format" in lesson_plan_columns:
        with op.batch_alter_table("lesson_plans") as batch_op:
            batch_op.drop_column("format")
    if "metadata_json" in learning_item_columns:
        with op.batch_alter_table("learning_items") as batch_op:
            batch_op.drop_column("metadata_json")


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}
