from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_epic23"
down_revision = "0001_epic22"
branch_labels = None
depends_on = None

TEMPLATE_TABLES = ("lesson_plans", "source_materials", "learning_items")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in TEMPLATE_TABLES:
        columns = _column_names(inspector, table_name)
        indexes = _index_names(inspector, table_name)
        if "is_template" not in columns:
            op.add_column(
                table_name,
                sa.Column(
                    "is_template",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "template_of" not in columns:
            op.add_column(
                table_name,
                sa.Column("template_of", sa.Integer(), nullable=True),
            )
        if f"ix_{table_name}_is_template" not in indexes:
            op.create_index(f"ix_{table_name}_is_template", table_name, ["is_template"])
        if f"ix_{table_name}_template_of" not in indexes:
            op.create_index(f"ix_{table_name}_template_of", table_name, ["template_of"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in reversed(TEMPLATE_TABLES):
        columns = _column_names(inspector, table_name)
        indexes = _index_names(inspector, table_name)
        if f"ix_{table_name}_template_of" in indexes:
            op.drop_index(f"ix_{table_name}_template_of", table_name=table_name)
        if f"ix_{table_name}_is_template" in indexes:
            op.drop_index(f"ix_{table_name}_is_template", table_name=table_name)
        with op.batch_alter_table(table_name) as batch_op:
            if "template_of" in columns:
                batch_op.drop_column("template_of")
            if "is_template" in columns:
                batch_op.drop_column("is_template")


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}
